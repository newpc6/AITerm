package api

import (
	"context"
	"fmt"
	"strings"
	"time"
)

func buildClosedEventStream(events ...sseEvent) <-chan sseEvent {
	stream := make(chan sseEvent, len(events))
	for _, event := range events {
		stream <- event
	}
	close(stream)
	return stream
}

func (s *appStore) markTaskStopped(taskID, summary string, stepIndex int) (taskItem, bool) {
	return s.mutateTask(taskID, func(item *taskItem) {
		item.Status = "cancelled"
		item.Progress = 100
		item.Summary = strings.TrimSpace(summary)
		if item.Summary == "" {
			item.Summary = "任务已停止。"
		}
		item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
		for index := range item.Steps {
			if item.Steps[index].Status == "completed" || item.Steps[index].Status == "failed" {
				continue
			}
			if stepIndex >= 0 && index == stepIndex {
				item.Steps[index].Status = "cancelled"
				continue
			}
			if item.Steps[index].Status != "completed" {
				item.Steps[index].Status = "cancelled"
			}
		}
	})
}

func (s *appStore) stopTaskExecution(taskID string, stream chan<- sseEvent, summary string, stepIndex int) {
	task, ok := s.markTaskStopped(taskID, summary, stepIndex)
	if !ok {
		return
	}
	stream <- buildTaskStatusEvent(task)
	stopMessage := strings.TrimSpace(summary)
	if stopMessage == "" {
		stopMessage = "任务已停止。"
	}
	s.appendConversationMessage(task.ConversationID, "assistant", stopMessage)
	stream <- buildTaskOutputEvent(task.ID, "stderr", stopMessage)
}

func (s *appStore) runTaskExecution(ctx context.Context, taskID string, skipPlanning bool, stream chan<- sseEvent) {
	defer close(stream)
	defer s.finishTaskExecution(taskID)

	task, ok := s.getTask(taskID)
	if !ok {
		return
	}
	node, _ := s.getNode(task.NodeID)
	nodeLabel := describeNode(node)
	settings := s.getLLMSettings()
	executionOutputs := make([]string, 0, 8)

	stream <- buildTaskStatusEvent(task)

	if !skipPlanning {
		if ctx.Err() != nil || s.isTaskStopRequested(taskID) {
			s.stopTaskExecution(taskID, stream, "任务已停止。", -1)
			return
		}

		planningTask, settings, planningNode, history, ok := s.prepareTaskPlanning(taskID)
		if !ok {
			return
		}

		planningMessage := fmt.Sprintf("正在结合节点 %s 分析任务并生成执行计划...", nodeLabel)
		s.appendConversationMessage(task.ConversationID, "assistant", planningMessage)
		stream <- buildTaskOutputEvent(task.ID, "stdout", planningMessage)

		plan, err := generateTaskPlan(ctx, settings, planningNode, history, planningTask.Request)
		if err != nil {
			if ctx.Err() != nil || s.isTaskStopRequested(taskID) {
				s.stopTaskExecution(taskID, stream, "任务已停止。", -1)
				return
			}

			task, ok = s.mutateTask(taskID, func(item *taskItem) {
				item.Status = "failed"
				item.Progress = 100
				item.Summary = fmt.Sprintf("节点 %s 的任务规划失败：%s", nodeLabel, strings.TrimSpace(err.Error()))
				item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
			})
			if !ok {
				return
			}
			stream <- buildTaskStatusEvent(task)
			errorText := fmt.Sprintf("任务规划失败: %s", strings.TrimSpace(err.Error()))
			s.appendConversationMessage(task.ConversationID, "assistant", errorText)
			stream <- buildTaskOutputEvent(task.ID, "stderr", errorText)
			return
		}

		riskReason := buildRiskReasonFromPlan(plan, settings)
		plannedSteps := buildTaskStepsFromPlan(plan.Steps)
		pendingPreview := buildPendingCommandPreview(plan.Steps)
		if ctx.Err() != nil || s.isTaskStopRequested(taskID) {
			s.stopTaskExecution(taskID, stream, "任务已停止。", -1)
			return
		}
		task, ok = s.mutateTask(taskID, func(item *taskItem) {
			item.Title = strings.TrimSpace(plan.Title)
			if item.Title == "" {
				item.Title = buildTaskTitle(item.Request, planningNode)
			}
			item.PendingCommand = pendingPreview
			item.RiskReason = riskReason
			item.Summary = strings.TrimSpace(plan.Summary)
			item.Steps = plannedSteps
			item.Progress = 45
			item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
			if riskReason != "" {
				item.Status = "waiting_confirm"
				item.Summary = fmt.Sprintf("%s 该计划需要人工确认后才会执行。", strings.TrimSpace(item.Summary))
				for index := range item.Steps {
					item.Steps[index].Status = "waiting_confirm"
				}
				return
			}
			item.Status = "executing"
		})
		if !ok {
			return
		}

		stream <- buildTaskStatusEvent(task)
		plannedMessage := fmt.Sprintf("已生成 %d 个执行步骤。", len(task.Steps))
		s.appendConversationMessage(task.ConversationID, "assistant", plannedMessage)
		stream <- buildTaskOutputEvent(task.ID, "plan.info", plannedMessage)
		planMessage := fmt.Sprintf("任务计划如下：\n%s", task.PendingCommand)
		s.appendConversationMessage(task.ConversationID, "assistant", planMessage)
		stream <- buildTaskOutputEvent(task.ID, "plan", task.PendingCommand)
		if task.Status == "waiting_confirm" {
			confirmMessage := fmt.Sprintf("该任务需要人工确认后执行。\n%s", task.PendingCommand)
			s.appendConversationMessage(task.ConversationID, "assistant", confirmMessage)
			stream <- buildTaskOutputEvent(task.ID, "approval", confirmMessage)
			return
		}
	}

	if len(task.Steps) == 0 {
		task, ok = s.mutateTask(taskID, func(item *taskItem) {
			item.Status = "failed"
			item.Progress = 100
			item.Summary = "任务缺少可执行步骤。"
			item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
		})
		if !ok {
			return
		}
		stream <- buildTaskStatusEvent(task)
		s.appendConversationMessage(task.ConversationID, "assistant", "任务缺少可执行步骤。")
		stream <- buildTaskOutputEvent(task.ID, "stderr", "任务缺少可执行步骤。")
		return
	}

	for index, step := range task.Steps {
		currentStep := step
		autoRepaired := false

		for {
			if ctx.Err() != nil || s.isTaskStopRequested(taskID) {
				s.stopTaskExecution(taskID, stream, "任务已停止。", index)
				return
			}
			if strings.TrimSpace(currentStep.Command) == "" {
				break
			}

			task, ok = s.mutateTask(taskID, func(item *taskItem) {
				item.Status = "executing"
				item.Progress = taskStepProgress(index, len(item.Steps), false)
				item.Summary = fmt.Sprintf("正在执行第 %d/%d 步：%s", index+1, len(item.Steps), currentStep.Title)
				item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
				for stepIndex := range item.Steps {
					switch {
					case stepIndex < index && item.Steps[stepIndex].Status != "completed":
						item.Steps[stepIndex].Status = "completed"
					case stepIndex == index:
						item.Steps[stepIndex] = currentStep
						item.Steps[stepIndex].Status = "executing"
					case item.Steps[stepIndex].Status == "waiting_confirm":
						item.Steps[stepIndex].Status = "pending"
					}
				}
			})
			if !ok {
				return
			}
			stream <- buildTaskStatusEvent(task)

			startMessage := fmt.Sprintf("开始执行第 %d 步：%s\n命令：%s", index+1, currentStep.Title, currentStep.Command)
			s.appendConversationMessage(task.ConversationID, "assistant", startMessage)
			stream <- buildTaskOutputEvent(task.ID, "step.start", startMessage)

			result := executeCommand(ctx, currentStep.Command)
			stepOutputs := make([]string, 0, len(result.Lines)+1)
			for _, line := range result.Lines {
				lineText := fmt.Sprintf("[%s] %s", line.Stream, line.Content)
				executionOutputs = append(executionOutputs, lineText)
				stepOutputs = append(stepOutputs, lineText)
				s.appendConversationMessage(task.ConversationID, "assistant", lineText)
				stream <- buildTaskOutputEvent(task.ID, line.Stream, line.Content)
			}
			stepOutputText := strings.TrimSpace(strings.Join(stepOutputs, "\n"))
			if autoRepaired {
				currentStep.RepairedOutput = stepOutputText
			} else {
				currentStep.ResultOutput = stepOutputText
			}

			if ctx.Err() != nil || s.isTaskStopRequested(taskID) {
				s.stopTaskExecution(taskID, stream, "任务已停止。", index)
				return
			}

			if result.ExitCode != 0 || result.Err != nil {
				if ctx.Err() != nil || s.isTaskStopRequested(taskID) {
					s.stopTaskExecution(taskID, stream, "任务已停止。", index)
					return
				}

				errorText := "命令执行失败。"
				if result.TimedOut {
					errorText = "命令执行超时，任务已被终止。"
				} else if result.Err != nil {
					errorText = fmt.Sprintf("命令执行失败: %s", strings.TrimSpace(result.Err.Error()))
				}
				stepOutputs = append(stepOutputs, errorText)
				s.appendConversationMessage(task.ConversationID, "assistant", errorText)
				stream <- buildTaskOutputEvent(task.ID, "stderr", errorText)

				var repairResult taskFailureRepairResult
				var repairErr error
				if !autoRepaired && !result.TimedOut {
					repairResult, repairErr = repairTaskExecutionFailure(ctx, settings, node, task.Request, currentStep, stepOutputs, errorText)
					if repairErr == nil && (repairResult.Reason != "" || repairResult.Suggestion != "") {
						analysisText := fmt.Sprintf("失败复盘：原因：%s", repairResult.Reason)
						if repairResult.Suggestion != "" {
							analysisText += fmt.Sprintf("；建议：%s", repairResult.Suggestion)
						}
						s.appendConversationMessage(task.ConversationID, "assistant", analysisText)
						stream <- buildTaskOutputEvent(task.ID, "repair.analysis", analysisText)
					}

					correctedCommand := strings.TrimSpace(repairResult.CorrectedCommand)
					if correctedCommand != "" && correctedCommand != currentStep.Command {
						originalCommand := currentStep.Command
						correctedTitle := currentStep.Title
						if strings.TrimSpace(repairResult.CorrectedTitle) != "" {
							correctedTitle = strings.TrimSpace(repairResult.CorrectedTitle)
						}
						task, ok = s.mutateTask(taskID, func(item *taskItem) {
							item.Status = "executing"
							item.Progress = taskStepProgress(index, len(item.Steps), false)
							item.Summary = fmt.Sprintf("第 %d/%d 步首次失败，已自动修正命令并准备重试。", index+1, len(item.Steps))
							item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
							if index < len(item.Steps) {
								item.Steps[index].Title = correctedTitle
								item.Steps[index].Command = correctedCommand
								item.Steps[index].Status = "executing"
								item.Steps[index].RepairCount++
								if strings.TrimSpace(item.Steps[index].OriginalCommand) == "" {
									item.Steps[index].OriginalCommand = strings.TrimSpace(originalCommand)
								}
								item.Steps[index].FirstFailureOutput = stepOutputText
								item.Steps[index].LastError = strings.TrimSpace(errorText)
								item.Steps[index].RepairReason = strings.TrimSpace(repairResult.Reason)
								item.Steps[index].RepairSuggestion = strings.TrimSpace(repairResult.Suggestion)
								item.Steps[index].RepairedCommand = correctedCommand
							}
						})
						if !ok {
							return
						}
						stream <- buildTaskStatusEvent(task)

						retryMessage := fmt.Sprintf("第 %d 步首次失败，已自动复盘并修正命令，继续执行：%s: %s", index+1, correctedTitle, correctedCommand)
						s.appendConversationMessage(task.ConversationID, "assistant", retryMessage)
						stream <- buildTaskOutputEvent(task.ID, "repair.retry", retryMessage)

						currentStep.Title = correctedTitle
						currentStep.Command = correctedCommand
						currentStep.RepairCount++
						if strings.TrimSpace(currentStep.OriginalCommand) == "" {
							currentStep.OriginalCommand = strings.TrimSpace(originalCommand)
						}
						currentStep.FirstFailureOutput = stepOutputText
						currentStep.LastError = strings.TrimSpace(errorText)
						currentStep.RepairReason = strings.TrimSpace(repairResult.Reason)
						currentStep.RepairSuggestion = strings.TrimSpace(repairResult.Suggestion)
						currentStep.RepairedCommand = correctedCommand
						autoRepaired = true
						continue
					}
					if repairErr == nil {
						noCommandMessage := fmt.Sprintf("第 %d 步自动复盘后未生成可执行的修正命令，任务停止。", index+1)
						s.appendConversationMessage(task.ConversationID, "assistant", noCommandMessage)
						stream <- buildTaskOutputEvent(task.ID, "repair.stop", noCommandMessage)
					}
				}

				task, ok = s.mutateTask(taskID, func(item *taskItem) {
					item.Status = "failed"
					item.Progress = 100
					item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
					if index < len(item.Steps) {
						item.Steps[index] = currentStep
						item.Steps[index].Status = "failed"
						if autoRepaired && strings.TrimSpace(item.Steps[index].ResultOutput) == "" {
							item.Steps[index].ResultOutput = stepOutputText
						}
						if !autoRepaired && strings.TrimSpace(item.Steps[index].FirstFailureOutput) == "" {
							item.Steps[index].FirstFailureOutput = stepOutputText
						}
						if autoRepaired && strings.TrimSpace(item.Steps[index].RepairedOutput) == "" {
							item.Steps[index].RepairedOutput = stepOutputText
						}
						item.Steps[index].LastError = strings.TrimSpace(errorText)
						if strings.TrimSpace(repairResult.Reason) != "" {
							item.Steps[index].RepairReason = strings.TrimSpace(repairResult.Reason)
						}
						if strings.TrimSpace(repairResult.Suggestion) != "" {
							item.Steps[index].RepairSuggestion = strings.TrimSpace(repairResult.Suggestion)
						}
					}
					switch {
					case result.TimedOut:
						item.Summary = fmt.Sprintf("节点 %s 上的第 %d 步执行超时，任务已被终止。", nodeLabel, index+1)
					case repairErr == nil && strings.TrimSpace(repairResult.Reason) != "":
						item.Summary = strings.TrimSpace(repairResult.Reason)
					default:
						item.Summary = fmt.Sprintf("节点 %s 上的第 %d 步执行失败，退出码 %d。", nodeLabel, index+1, result.ExitCode)
					}
				})
				if !ok {
					return
				}
				stream <- buildTaskStatusEvent(task)
				return
			}

			stepResultMessage := fmt.Sprintf("第 %d 步执行结果：\n%s", index+1, stepOutputText)
			if strings.TrimSpace(stepOutputText) != "" {
				s.appendConversationMessage(task.ConversationID, "assistant", stepResultMessage)
				stream <- buildTaskOutputEvent(task.ID, "step.result", stepResultMessage)
			}

			task, ok = s.mutateTask(taskID, func(item *taskItem) {
				item.Progress = taskStepProgress(index, len(item.Steps), true)
				item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
				if index < len(item.Steps) {
					item.Steps[index] = currentStep
					item.Steps[index].Status = "completed"
					if autoRepaired {
						item.Steps[index].ResultOutput = strings.TrimSpace(currentStep.RepairedOutput)
					} else {
						item.Steps[index].ResultOutput = stepOutputText
					}
				}
			})
			if !ok {
				return
			}
			stream <- buildTaskStatusEvent(task)
			break
		}
	}

	if ctx.Err() != nil || s.isTaskStopRequested(taskID) {
		s.stopTaskExecution(taskID, stream, "任务已停止。", -1)
		return
	}

	task, ok = s.mutateTask(taskID, func(item *taskItem) {
		item.Status = "completed"
		item.Progress = 100
		item.Summary = fmt.Sprintf("节点 %s 上的任务已完成，执行计划中的步骤均已运行。", nodeLabel)
		item.FinalResult = ""
		item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	})
	if !ok {
		return
	}
	stream <- buildTaskStatusEvent(task)
	if summary, err := summarizeTaskExecution(ctx, settings, node, task.Request, task.Steps, executionOutputs); err == nil && strings.TrimSpace(summary) != "" {
		finalMessage := fmt.Sprintf("任务最终结果：\n%s", summary)
		s.appendConversationMessage(task.ConversationID, "assistant", finalMessage)
		stream <- buildTaskOutputEvent(task.ID, "summary", finalMessage)
		task, ok = s.mutateTask(taskID, func(item *taskItem) {
			item.Summary = strings.TrimSpace(summary)
			item.FinalResult = strings.TrimSpace(summary)
			item.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
		})
		if ok {
			stream <- buildTaskStatusEvent(task)
		}
	}
}

func buildTaskStatusEvent(task taskItem) sseEvent {
	return sseEvent{
		Event: "task.status",
		Data: map[string]interface{}{
			"task_id":  task.ID,
			"status":   task.Status,
			"progress": task.Progress,
		},
	}
}

func buildTaskOutputEvent(taskID, streamName, content string) sseEvent {
	return sseEvent{
		Event: "task.output",
		Data: map[string]interface{}{
			"task_id": taskID,
			"stream":  streamName,
			"content": content,
		},
	}
}

func (s *appStore) mutateTask(taskID string, mutate func(*taskItem)) (taskItem, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, ok := s.tasks[taskID]
	if !ok {
		return taskItem{}, false
	}

	mutate(&task)
	s.tasks[task.ID] = task
	s.persistAllLocked()
	return cloneTask(task), true
}

func taskStepProgress(index, total int, completed bool) int {
	if total <= 0 {
		if completed {
			return 100
		}
		return 55
	}

	base := 55
	if completed {
		return base + int(float64(index+1)/float64(total)*45)
	}
	return base + int(float64(index)/float64(total)*35)
}
