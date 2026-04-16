package api

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"
)

type llmChatRequest struct {
	Model       string           `json:"model"`
	Messages    []llmChatMessage `json:"messages"`
	Temperature float64          `json:"temperature"`
	Stream      bool             `json:"stream,omitempty"`
}

type llmChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type llmChatResponse struct {
	Choices []struct {
		Message struct {
			Content interface{} `json:"content"`
		} `json:"message"`
	} `json:"choices"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

type llmChatChunkResponse struct {
	Choices []struct {
		Delta struct {
			Content interface{} `json:"content"`
		} `json:"delta"`
		Message struct {
			Content interface{} `json:"content"`
		} `json:"message"`
	} `json:"choices"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

func generateChatReply(settings llmSettings, node nodeItem, history []conversationMessageItem, message string) (string, error) {
	if strings.TrimSpace(settings.APIURL) == "" || strings.TrimSpace(settings.Model) == "" {
		return "", fmt.Errorf("LLM 设置未完成，请先在设置页填写 API 地址和模型")
	}

	payload, err := buildLLMRequestPayload(settings, node, history, message, false)
	if err != nil {
		return "", err
	}
	req, err := http.NewRequest(http.MethodPost, buildChatCompletionsURL(settings.APIURL), bytes.NewReader(payload))
	if err != nil {
		return "", err
	}
	applyLLMRequestHeaders(req, settings)
	client := &http.Client{Timeout: 45 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	return parseLLMChatResponse(resp.StatusCode, body)
}

func summarizeTaskExecution(ctx context.Context, settings llmSettings, node nodeItem, request string, steps []taskStep, outputs []string) (string, error) {
	if strings.TrimSpace(settings.APIURL) == "" || strings.TrimSpace(settings.Model) == "" {
		return "", fmt.Errorf("LLM 设置未完成，请先在设置页填写 API 地址和模型")
	}

	var builder strings.Builder
	builder.WriteString("请根据以下任务执行信息，用中文输出一段简洁、准确的结果总结。")
	builder.WriteString("\n要求：")
	builder.WriteString("\n1. 用 2 到 4 句话总结执行结果。")
	builder.WriteString("\n2. 如果输出里包含数值、容量、状态等关键信息，要提炼出来。")
	builder.WriteString("\n3. 不要重复原始日志，不要输出 markdown 列表。")
	builder.WriteString("\n4. 如果结果不完整，要明确指出。")
	builder.WriteString("\n\n任务请求：")
	builder.WriteString(strings.TrimSpace(request))
	builder.WriteString("\n节点：")
	builder.WriteString(describeNode(node))
	if len(steps) > 0 {
		builder.WriteString("\n\n执行步骤：")
		for _, step := range steps {
			builder.WriteString("\n- ")
			builder.WriteString(step.Title)
			builder.WriteString(" [")
			builder.WriteString(step.Status)
			builder.WriteString("]: ")
			builder.WriteString(strings.TrimSpace(step.Command))
		}
	}
	if len(outputs) > 0 {
		builder.WriteString("\n\n执行输出：")
		for _, output := range outputs {
			builder.WriteString("\n- ")
			builder.WriteString(strings.TrimSpace(output))
		}
	}

	requestBody := llmChatRequest{
		Model: settings.Model,
		Messages: []llmChatMessage{
			{
				Role:    "system",
				Content: "你是一个任务执行结果整理助手，只根据给定的任务信息输出简洁结论。",
			},
			{
				Role:    "user",
				Content: builder.String(),
			},
		},
		Temperature: 0.2,
	}

	payload, err := json.Marshal(requestBody)
	if err != nil {
		return "", err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, buildChatCompletionsURL(settings.APIURL), bytes.NewReader(payload))
	if err != nil {
		return "", err
	}
	applyLLMRequestHeaders(req, settings)
	client := &http.Client{Timeout: 45 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	return parseLLMChatResponse(resp.StatusCode, body)
}

type taskFailureRepairResult struct {
	Reason           string `json:"reason"`
	Suggestion       string `json:"suggestion"`
	CorrectedTitle   string `json:"corrected_title"`
	CorrectedCommand string `json:"corrected_command"`
}

func repairTaskExecutionFailure(ctx context.Context, settings llmSettings, node nodeItem, request string, step taskStep, outputs []string, failureText string) (taskFailureRepairResult, error) {
	if strings.TrimSpace(settings.APIURL) == "" || strings.TrimSpace(settings.Model) == "" {
		return taskFailureRepairResult{}, fmt.Errorf("LLM 设置未完成，请先在设置页填写 API 地址和模型")
	}

	prompt := buildTaskFailureRepairPrompt(settings, node, request, step, outputs, failureText)

	requestBody := llmChatRequest{
		Model: settings.Model,
		Messages: []llmChatMessage{
			{
				Role:    "user",
				Content: prompt,
			},
		},
		Temperature: 0.2,
	}

	payload, err := json.Marshal(requestBody)
	if err != nil {
		return taskFailureRepairResult{}, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, buildChatCompletionsURL(settings.APIURL), bytes.NewReader(payload))
	if err != nil {
		return taskFailureRepairResult{}, err
	}
	applyLLMRequestHeaders(req, settings)
	client := &http.Client{Timeout: 45 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return taskFailureRepairResult{}, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return taskFailureRepairResult{}, err
	}

	content, err := parseLLMChatResponse(resp.StatusCode, body)
	if err != nil {
		return taskFailureRepairResult{}, err
	}
	result, err := parseTaskFailureRepairResult(content)
	if err != nil {
		return taskFailureRepairResult{}, err
	}
	if strings.TrimSpace(result.CorrectedCommand) == "" {
		result.CorrectedCommand = inferCorrectedCommandFromRepairText(step.Command, result.Suggestion, result.Reason, content)
	}
	return result, nil
}

func buildTaskFailureRepairPrompt(settings llmSettings, node nodeItem, request string, step taskStep, outputs []string, failureText string) string {
	template := strings.TrimSpace(settings.TaskFailureRepairPrompt)
	if template == "" {
		template = "请分析以下自动化任务失败信息，并返回修正结果。任务请求：{{user_request}}\n节点：{{node_description}}\n失败步骤：{{step_title}}\n失败命令：{{failed_command}}\n执行输出：{{execution_output}}\n失败提示：{{failure_text}}"
	}

	outputText := "无输出"
	if len(outputs) > 0 {
		outputText = strings.Join(outputs, "\n")
	}

	replacer := strings.NewReplacer(
		"{{node_name}}", strings.TrimSpace(node.Name),
		"{{node_host}}", strings.TrimSpace(node.Host),
		"{{node_port}}", fmt.Sprintf("%d", node.Port),
		"{{node_status}}", strings.TrimSpace(node.Status),
		"{{node_description}}", describeNode(node),
		"{{user_request}}", strings.TrimSpace(request),
		"{{step_title}}", strings.TrimSpace(step.Title),
		"{{failed_command}}", strings.TrimSpace(step.Command),
		"{{execution_output}}", strings.TrimSpace(outputText),
		"{{failure_text}}", strings.TrimSpace(failureText),
	)
	return replacer.Replace(template)
}

func parseTaskFailureRepairResult(raw string) (taskFailureRepairResult, error) {
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

	var result taskFailureRepairResult
	if err := json.Unmarshal([]byte(cleaned), &result); err != nil {
		repaired := repairMalformedTaskPlanJSON(cleaned)
		if repairErr := json.Unmarshal([]byte(repaired), &result); repairErr != nil {
			return taskFailureRepairResult{}, fmt.Errorf("任务失败修正结果无法解析: %s", cleaned)
		}
	}

	result.Reason = strings.TrimSpace(result.Reason)
	result.Suggestion = strings.TrimSpace(result.Suggestion)
	result.CorrectedTitle = strings.TrimSpace(result.CorrectedTitle)
	result.CorrectedCommand = strings.TrimSpace(result.CorrectedCommand)
	return result, nil
}

var inlineCodePattern = regexp.MustCompile("`([^`\\r\\n]+)`")

func inferCorrectedCommandFromRepairText(failedCommand string, texts ...string) string {
	baseCommand := strings.ToLower(strings.TrimSpace(firstCommandToken(failedCommand)))
	if baseCommand == "" {
		baseCommand = strings.ToLower(strings.TrimSpace(failedCommand))
	}

	candidates := make([]string, 0, 4)
	for _, text := range texts {
		matches := inlineCodePattern.FindAllStringSubmatch(text, -1)
		for _, match := range matches {
			if len(match) < 2 {
				continue
			}
			candidate := sanitizeRepairCommandCandidate(match[1])
			if candidate == "" {
				continue
			}
			candidates = append(candidates, candidate)
		}
	}

	for _, candidate := range candidates {
		candidateBase := strings.ToLower(firstCommandToken(candidate))
		if baseCommand != "" && candidateBase == baseCommand {
			return candidate
		}
	}

	for _, candidate := range candidates {
		if looksExecutableRepairCommand(candidate) {
			return candidate
		}
	}

	return ""
}

func sanitizeRepairCommandCandidate(value string) string {
	candidate := strings.TrimSpace(value)
	candidate = strings.Trim(candidate, "\"'")
	if candidate == "" {
		return ""
	}
	if strings.ContainsAny(candidate, "{}") {
		return ""
	}
	if strings.Contains(strings.ToLower(candidate), "corrected_command") {
		return ""
	}
	return strings.TrimSpace(candidate)
}

func looksExecutableRepairCommand(candidate string) bool {
	if candidate == "" {
		return false
	}
	if len(candidate) > 300 {
		return false
	}
	lower := strings.ToLower(candidate)
	switch lower {
	case "json", "markdown", "reason", "suggestion":
		return false
	}
	return true
}

func firstCommandToken(command string) string {
	fields := strings.Fields(strings.TrimSpace(command))
	if len(fields) == 0 {
		return ""
	}
	return strings.Trim(fields[0], "\"'")
}

func streamChatReply(ctx context.Context, settings llmSettings, node nodeItem, history []conversationMessageItem, message string, emit func(string) error) (string, error) {
	if strings.TrimSpace(settings.APIURL) == "" || strings.TrimSpace(settings.Model) == "" {
		return "", fmt.Errorf("LLM 设置未完成，请先在设置页填写 API 地址和模型")
	}

	payload, err := buildLLMRequestPayload(settings, node, history, message, true)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, buildChatCompletionsURL(settings.APIURL), bytes.NewReader(payload))
	if err != nil {
		return "", err
	}
	applyLLMRequestHeaders(req, settings)

	client := &http.Client{Timeout: 90 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	contentType := strings.ToLower(resp.Header.Get("Content-Type"))
	if resp.StatusCode >= 400 || !strings.Contains(contentType, "text/event-stream") {
		body, readErr := io.ReadAll(resp.Body)
		if readErr != nil {
			return "", readErr
		}
		reply, parseErr := parseLLMChatResponse(resp.StatusCode, body)
		if parseErr != nil {
			return "", parseErr
		}
		if emit != nil {
			if err := emit(reply); err != nil {
				return "", err
			}
		}
		return reply, nil
	}

	reader := bufio.NewReader(resp.Body)
	var builder strings.Builder
	dataLines := make([]string, 0, 4)

	flushData := func() error {
		if len(dataLines) == 0 {
			return nil
		}
		payload := strings.TrimSpace(strings.Join(dataLines, "\n"))
		dataLines = dataLines[:0]
		if payload == "" {
			return nil
		}
		if payload == "[DONE]" {
			return io.EOF
		}

		var chunk llmChatChunkResponse
		if err := json.Unmarshal([]byte(payload), &chunk); err != nil {
			return fmt.Errorf("模型流式返回无法解析: %s", payload)
		}
		if chunk.Error != nil && strings.TrimSpace(chunk.Error.Message) != "" {
			return fmt.Errorf(chunk.Error.Message)
		}
		if len(chunk.Choices) == 0 {
			return nil
		}

		text := extractLLMContent(chunk.Choices[0].Delta.Content)
		if strings.TrimSpace(text) == "" {
			text = extractLLMContent(chunk.Choices[0].Message.Content)
		}
		if text == "" {
			return nil
		}

		builder.WriteString(text)
		if emit != nil {
			return emit(text)
		}
		return nil
	}

	for {
		line, readErr := reader.ReadString('\n')
		if readErr != nil && readErr != io.EOF {
			return "", readErr
		}

		trimmed := strings.TrimRight(line, "\r\n")
		if trimmed == "" {
			if err := flushData(); err != nil {
				if err == io.EOF {
					break
				}
				return "", err
			}
		} else if strings.HasPrefix(trimmed, "data:") {
			dataLines = append(dataLines, strings.TrimSpace(strings.TrimPrefix(trimmed, "data:")))
		}

		if readErr == io.EOF {
			if err := flushData(); err != nil && err != io.EOF {
				return "", err
			}
			break
		}
	}

	reply := strings.TrimSpace(builder.String())
	if reply == "" {
		return "", fmt.Errorf("模型返回内容为空")
	}
	return reply, nil
}

func buildLLMRequestPayload(settings llmSettings, node nodeItem, history []conversationMessageItem, message string, stream bool) ([]byte, error) {
	requestBody := llmChatRequest{
		Model:       strings.TrimSpace(settings.Model),
		Messages:    buildLLMMessages(settings, history, node, message),
		Temperature: settings.Temperature,
		Stream:      stream,
	}
	if requestBody.Temperature == 0 {
		requestBody.Temperature = 0.7
	}
	return json.Marshal(requestBody)
}

func applyLLMRequestHeaders(req *http.Request, settings llmSettings) {
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json, text/event-stream")
	if strings.TrimSpace(settings.APIKey) != "" {
		req.Header.Set("Authorization", "Bearer "+strings.TrimSpace(settings.APIKey))
	}
}

func parseLLMChatResponse(statusCode int, body []byte) (string, error) {
	var chatResponse llmChatResponse
	if err := json.Unmarshal(body, &chatResponse); err != nil {
		return "", fmt.Errorf("模型返回无法解析: %s", strings.TrimSpace(string(body)))
	}

	if statusCode >= 400 {
		if chatResponse.Error != nil && strings.TrimSpace(chatResponse.Error.Message) != "" {
			return "", fmt.Errorf(chatResponse.Error.Message)
		}
		return "", fmt.Errorf("模型请求失败: HTTP %d", statusCode)
	}

	if len(chatResponse.Choices) == 0 {
		return "", fmt.Errorf("模型未返回有效回复")
	}

	reply := extractLLMContent(chatResponse.Choices[0].Message.Content)
	if strings.TrimSpace(reply) == "" {
		return "", fmt.Errorf("模型返回内容为空")
	}

	return reply, nil
}

func buildLLMMessages(settings llmSettings, history []conversationMessageItem, node nodeItem, message string) []llmChatMessage {
	messages := []llmChatMessage{
		{
			Role:    "system",
			Content: buildChatSystemPrompt(settings, node, message),
		},
	}

	start := 0
	if len(history) > 12 {
		start = len(history) - 12
	}
	for _, item := range history[start:] {
		if item.Role != "user" && item.Role != "assistant" {
			continue
		}
		messages = append(messages, llmChatMessage{
			Role:    item.Role,
			Content: item.Content,
		})
	}

	messages = append(messages, llmChatMessage{
		Role:    "user",
		Content: message,
	})

	return messages
}

func buildChatSystemPrompt(settings llmSettings, node nodeItem, message string) string {
	template := strings.TrimSpace(settings.ChatSystemPrompt)
	if template == "" {
		template = "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。"
	}
	return renderPromptTemplate(template, node, message)
}

func buildChatCompletionsURL(apiURL string) string {
	trimmed := strings.TrimRight(strings.TrimSpace(apiURL), "/")
	if strings.HasSuffix(trimmed, "/chat/completions") {
		return trimmed
	}

	return trimmed + "/chat/completions"
}

func extractLLMContent(raw interface{}) string {
	switch value := raw.(type) {
	case string:
		return strings.TrimSpace(value)
	case []interface{}:
		parts := make([]string, 0, len(value))
		for _, item := range value {
			part, ok := item.(map[string]interface{})
			if !ok {
				continue
			}
			text, _ := part["text"].(string)
			if strings.TrimSpace(text) != "" {
				parts = append(parts, strings.TrimSpace(text))
			}
		}
		return strings.Join(parts, "\n")
	default:
		return ""
	}
}

func renderPromptTemplate(template string, node nodeItem, message string) string {
	replacer := strings.NewReplacer(
		"{{node_name}}", strings.TrimSpace(node.Name),
		"{{node_host}}", strings.TrimSpace(node.Host),
		"{{node_port}}", fmt.Sprintf("%d", node.Port),
		"{{node_status}}", strings.TrimSpace(node.Status),
		"{{node_description}}", describeNode(node),
		"{{user_request}}", strings.TrimSpace(message),
	)
	return replacer.Replace(strings.TrimSpace(template))
}
