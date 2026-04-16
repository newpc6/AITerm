package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"runtime"
	"strings"
	"time"
)

type taskPlanStep struct {
	Title   string `json:"title"`
	Command string `json:"command"`
}

type taskPlanResult struct {
	Title                string         `json:"title"`
	Summary              string         `json:"summary"`
	RequiresConfirmation bool           `json:"requires_confirmation"`
	RiskReason           string         `json:"risk_reason"`
	Steps                []taskPlanStep `json:"steps"`
}

func generateTaskPlan(ctx context.Context, settings llmSettings, node nodeItem, history []conversationMessageItem, message string) (taskPlanResult, error) {
	if strings.TrimSpace(settings.APIURL) == "" || strings.TrimSpace(settings.Model) == "" {
		return taskPlanResult{}, fmt.Errorf("LLM 设置未完成，请先在设置页填写 API 地址和模型")
	}

	requestBody := llmChatRequest{
		Model: settings.Model,
		Messages: []llmChatMessage{
			{
				Role:    "system",
				Content: buildTaskPlannerSystemPrompt(settings, node, message),
			},
			{
				Role:    "user",
				Content: buildTaskPlannerUserPrompt(settings, node, history, message),
			},
		},
		Temperature: settings.Temperature,
	}
	if requestBody.Temperature == 0 {
		requestBody.Temperature = 0.2
	}

	payload, err := json.Marshal(requestBody)
	if err != nil {
		return taskPlanResult{}, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, buildChatCompletionsURL(settings.APIURL), bytes.NewReader(payload))
	if err != nil {
		return taskPlanResult{}, err
	}
	applyLLMRequestHeaders(req, settings)

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return taskPlanResult{}, err
	}
	defer resp.Body.Close()

	reply, err := parseLLMChatResponse(resp.StatusCode, mustReadAll(resp))
	if err != nil {
		return taskPlanResult{}, err
	}

	return parseTaskPlan(reply)
}

func buildTaskPlannerSystemPrompt(settings llmSettings, node nodeItem, message string) string {
	template := strings.TrimSpace(settings.TaskPlannerPrompt)
	if template == "" {
		template = "你是一个任务规划器，请将用户请求转换为可执行任务计划。"
	}

	commandRulesText := buildTaskPlannerCommandRulesPrompt(settings)
	return renderPromptTemplate(template, node, message) + commandRulesText + "\n\n你必须只返回 JSON，不要输出 markdown，不要输出解释。JSON 结构固定为：{\"title\":\"\",\"summary\":\"\",\"requires_confirmation\":false,\"risk_reason\":\"\",\"steps\":[{\"title\":\"\",\"command\":\"\"}]}"
}

func buildTaskPlannerUserPrompt(settings llmSettings, node nodeItem, history []conversationMessageItem, message string) string {
	template := strings.TrimSpace(settings.TaskPlannerUserPrompt)
	if template == "" {
		template = "请基于以下用户请求生成任务计划，并为每一步提供可直接执行的命令。\n用户请求：{{user_request}}{{conversation_history}}\n\n要求：\n1. 返回 1 到 5 个可执行步骤。\n2. 每个步骤都要有简短 title 和 command。\n3. command 必须可直接在目标节点 shell 中执行，不要生成仅用于打开交互式终端的命令，例如 cmd.exe、powershell.exe、bash、sh。\n4. 如果用户明确指定了盘符、路径、服务名、端口、进程名等目标，必须严格保留，不要替换成其他值，也不要额外添加括号或占位符。\n5. 对于 Windows 场景，优先生成可一次性执行并直接返回结果的 PowerShell 或系统命令，不要依赖先打开 cmd 再继续输入；查询盘符空间时，优先使用 `Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='D:'\" | Select-Object DeviceID,FreeSpace,Size | Format-List` 这一类格式。\n6. 如果存在删除、覆盖、停止服务、重启、安装、卸载、数据库变更等风险，requires_confirmation 设为 true。\n7. summary 用中文概括执行目标和主要注意事项。"
	}

	historyText := buildTaskPlannerHistoryPrompt(history)
	platformName, platformPrompt := buildTaskPlannerPlatformToolPrompt(settings, node)
	replacer := strings.NewReplacer(
		"{{user_request}}", strings.TrimSpace(message),
		"{{conversation_history}}", historyText,
		"{{platform_name}}", platformName,
		"{{platform_tool_prompt}}", platformPrompt,
	)
	result := strings.TrimSpace(replacer.Replace(template))
	if platformPrompt == "" {
		return result
	}
	return strings.TrimSpace(result + "\n\n当前系统工具参考（" + platformName + "）：\n" + platformPrompt)
}

func buildTaskPlannerPlatformToolPrompt(settings llmSettings, node nodeItem) (string, string) {
	platform := detectTaskPlannerPlatform(node)
	switch platform {
	case "windows":
		return "Windows", strings.TrimSpace(settings.TaskWindowsToolPrompt)
	case "linux":
		return "Linux", strings.TrimSpace(settings.TaskLinuxToolPrompt)
	case "macos":
		return "macOS", strings.TrimSpace(settings.TaskMacToolPrompt)
	default:
		return "未知", ""
	}
}

func detectTaskPlannerPlatform(node nodeItem) string {
	host := strings.ToLower(strings.TrimSpace(node.Host))
	if node.ID == defaultLocalNodeID || host == "127.0.0.1" || host == "localhost" || host == "::1" {
		switch runtime.GOOS {
		case "windows":
			return "windows"
		case "linux":
			return "linux"
		case "darwin":
			return "macos"
		}
	}
	return ""
}

func buildTaskPlannerHistoryPrompt(history []conversationMessageItem) string {
	start := 0
	if len(history) > 6 {
		start = len(history) - 6
	}
	if len(history[start:]) == 0 {
		return ""
	}

	var builder strings.Builder
	builder.WriteString("\n\n最近对话上下文：")
	if len(history[start:]) > 0 {
		for _, item := range history[start:] {
			if item.Role != "user" && item.Role != "assistant" {
				continue
			}
			builder.WriteString("\n- ")
			builder.WriteString(item.Role)
			builder.WriteString(": ")
			builder.WriteString(strings.TrimSpace(item.Content))
		}
	}
	return builder.String()
}

func buildTaskPlannerCommandRulesPrompt(settings llmSettings) string {
	blacklist := normalizeCommandRules(settings.TaskCommandBlacklist)
	whitelist := normalizeCommandRules(settings.TaskCommandWhitelist)
	if len(blacklist) == 0 && len(whitelist) == 0 {
		return ""
	}

	commandRules := buildTaskPlannerCommandRulesBody(blacklist, whitelist)
	template := strings.TrimSpace(settings.TaskCommandRulesPrompt)
	if template == "" {
		template = "命令风控规则：{{command_rules}}"
	}

	replacer := strings.NewReplacer(
		"{{command_rules}}", commandRules,
		"{{blacklist}}", strings.Join(blacklist, "、"),
		"{{whitelist}}", strings.Join(whitelist, "、"),
	)
	return "\n\n" + strings.TrimSpace(replacer.Replace(template))
}

func buildTaskPlannerCommandRulesBody(blacklist []string, whitelist []string) string {
	var builder strings.Builder
	if len(blacklist) > 0 {
		builder.WriteString("\n- 以下命令片段命中后会强制人工确认，请尽量避免误触：")
		builder.WriteString(strings.Join(blacklist, "、"))
	}
	if len(whitelist) > 0 {
		builder.WriteString("\n- 以下命令片段属于白名单，可在生成命令时参考：")
		builder.WriteString(strings.Join(whitelist, "、"))
	}
	return strings.TrimSpace(builder.String())
}

func parseTaskPlan(raw string) (taskPlanResult, error) {
	cleaned := strings.TrimSpace(raw)
	cleaned = strings.TrimPrefix(cleaned, "```json")
	cleaned = strings.TrimPrefix(cleaned, "```")
	cleaned = strings.TrimSuffix(cleaned, "```")
	cleaned = strings.TrimSpace(cleaned)

	start := strings.Index(cleaned, "{")
	end := strings.LastIndex(cleaned, "}")
	if start >= 0 && end > start {
		cleaned = cleaned[start : end+1]
	}

	var plan taskPlanResult
	if err := json.Unmarshal([]byte(cleaned), &plan); err != nil {
		repaired := repairMalformedTaskPlanJSON(cleaned)
		if repairErr := json.Unmarshal([]byte(repaired), &plan); repairErr != nil {
			return taskPlanResult{}, fmt.Errorf("任务规划结果无法解析: %s", cleaned)
		}
	}

	plan.Title = strings.TrimSpace(plan.Title)
	plan.Summary = strings.TrimSpace(plan.Summary)
	plan.RiskReason = strings.TrimSpace(plan.RiskReason)
	filtered := make([]taskPlanStep, 0, len(plan.Steps))
	for _, step := range plan.Steps {
		command := strings.TrimSpace(step.Command)
		if command == "" {
			continue
		}
		filtered = append(filtered, taskPlanStep{
			Title:   strings.TrimSpace(step.Title),
			Command: command,
		})
	}
	plan.Steps = filtered

	if plan.Title == "" {
		plan.Title = "模型生成任务"
	}
	if plan.Summary == "" {
		plan.Summary = "模型已生成执行计划。"
	}
	if len(plan.Steps) == 0 {
		return taskPlanResult{}, fmt.Errorf("模型未生成可执行步骤")
	}

	return plan, nil
}

func repairMalformedTaskPlanJSON(raw string) string {
	var builder strings.Builder
	builder.Grow(len(raw) + 16)

	inString := false
	escaped := false
	for index := 0; index < len(raw); index++ {
		ch := raw[index]

		if !inString {
			builder.WriteByte(ch)
			if ch == '"' {
				inString = true
			}
			continue
		}

		if escaped {
			if !isValidJSONEscape(ch) {
				builder.WriteByte('\\')
			}
			builder.WriteByte(ch)
			escaped = false
			continue
		}

		if ch == '\\' {
			builder.WriteByte(ch)
			escaped = true
			continue
		}

		builder.WriteByte(ch)
		if ch == '"' {
			inString = false
		}
	}

	return builder.String()
}

func isValidJSONEscape(ch byte) bool {
	switch ch {
	case '"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u':
		return true
	default:
		return false
	}
}

func mustReadAll(resp *http.Response) []byte {
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return []byte{}
	}
	return body
}
