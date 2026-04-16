package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"

	"aiterm-server/internal/config"
)

type response struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data"`
}

type conversationRequest struct {
	ConversationID string `json:"conversation_id"`
	NodeID         string `json:"node_id"`
	Message        string `json:"message"`
	Mode           string `json:"mode"`
}

type conversationMessageItem struct {
	ID             string `json:"id"`
	ConversationID string `json:"conversation_id"`
	Role           string `json:"role"`
	Content        string `json:"content"`
	CreatedAt      string `json:"created_at"`
}

type conversationListItem struct {
	ID           string `json:"id"`
	Title        string `json:"title"`
	LastMessage  string `json:"last_message"`
	MessageCount int    `json:"message_count"`
	LatestTaskID string `json:"latest_task_id,omitempty"`
	LatestNodeID string `json:"latest_node_id,omitempty"`
	LatestStatus string `json:"latest_status,omitempty"`
	UpdatedAt    string `json:"updated_at"`
}

type taskStep struct {
	Index              int    `json:"index"`
	Title              string `json:"title"`
	Status             string `json:"status"`
	Command            string `json:"command"`
	ResultOutput       string `json:"result_output,omitempty"`
	RepairCount        int    `json:"repair_count,omitempty"`
	OriginalCommand    string `json:"original_command,omitempty"`
	FirstFailureOutput string `json:"first_failure_output,omitempty"`
	RepairedOutput     string `json:"repaired_output,omitempty"`
	LastError          string `json:"last_error,omitempty"`
	RepairReason       string `json:"repair_reason,omitempty"`
	RepairSuggestion   string `json:"repair_suggestion,omitempty"`
	RepairedCommand    string `json:"repaired_command,omitempty"`
}

type taskItem struct {
	ID             string     `json:"id"`
	Title          string     `json:"title"`
	Status         string     `json:"status"`
	Progress       int        `json:"progress"`
	ConversationID string     `json:"conversation_id"`
	NodeID         string     `json:"node_id"`
	Request        string     `json:"request,omitempty"`
	PendingCommand string     `json:"pending_command,omitempty"`
	RiskReason     string     `json:"risk_reason,omitempty"`
	Summary        string     `json:"summary,omitempty"`
	FinalResult    string     `json:"final_result,omitempty"`
	Steps          []taskStep `json:"steps,omitempty"`
	CreatedAt      string     `json:"created_at"`
	UpdatedAt      string     `json:"updated_at,omitempty"`
}

type nodeItem struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Host   string `json:"host"`
	Port   int    `json:"port"`
	Status string `json:"status"`
}

type llmSettings struct {
	APIURL                  string   `json:"api_url"`
	APIKey                  string   `json:"api_key"`
	Model                   string   `json:"model"`
	Temperature             float64  `json:"temperature"`
	ChatSystemPrompt        string   `json:"chat_system_prompt"`
	TaskPlannerPrompt       string   `json:"task_planner_prompt"`
	TaskPlannerUserPrompt   string   `json:"task_planner_user_prompt"`
	TaskWindowsToolPrompt   string   `json:"task_windows_tool_prompt"`
	TaskLinuxToolPrompt     string   `json:"task_linux_tool_prompt"`
	TaskMacToolPrompt       string   `json:"task_mac_tool_prompt"`
	TaskFailureRepairPrompt string   `json:"task_failure_repair_prompt"`
	TaskCommandRulesPrompt  string   `json:"task_command_rules_prompt"`
	TaskCommandBlacklist    []string `json:"task_command_blacklist"`
	TaskCommandWhitelist    []string `json:"task_command_whitelist"`
	Configured              bool     `json:"configured"`
}

type llmPublicInfo struct {
	Model      string `json:"model"`
	Configured bool   `json:"configured"`
}

type authSettings struct {
	Enabled            bool `json:"enabled"`
	AllowPasswordLogin bool `json:"allow_password_login"`
	SessionTTLHours    int  `json:"session_ttl_hours"`
}

type nodeRequest struct {
	Name string `json:"name"`
	Host string `json:"host"`
	Port int    `json:"port"`
}

type userItem struct {
	ID           string `json:"id"`
	Username     string `json:"username"`
	DisplayName  string `json:"display_name"`
	Role         string `json:"role"`
	Status       string `json:"status"`
	LastLoginAt  string `json:"last_login_at,omitempty"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
	PasswordHash string `json:"-"`
}

type userRequest struct {
	Username    string `json:"username"`
	DisplayName string `json:"display_name"`
	Password    string `json:"password"`
	Role        string `json:"role"`
	Status      string `json:"status"`
}

type userUpdateRequest struct {
	DisplayName string `json:"display_name"`
	Role        string `json:"role"`
	Status      string `json:"status"`
}

type authLoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type authChangePasswordRequest struct {
	CurrentPassword string `json:"current_password"`
	NewPassword     string `json:"new_password"`
}

type userResetPasswordRequest struct {
	Password string `json:"password"`
}

type sessionItem struct {
	ID        string `json:"id"`
	Token     string `json:"token"`
	UserID    string `json:"user_id"`
	CreatedAt string `json:"created_at"`
	ExpiresAt string `json:"expires_at"`
}

type authLoginData struct {
	Token     string   `json:"token"`
	ExpiresAt string   `json:"expires_at"`
	User      userItem `json:"user"`
}

type authStatusData struct {
	Enabled            bool      `json:"enabled"`
	AllowPasswordLogin bool      `json:"allow_password_login"`
	Authenticated      bool      `json:"authenticated"`
	User               *userItem `json:"user,omitempty"`
}

type taskConfirmRequest struct {
	Approved bool `json:"approved"`
}

type sseEvent struct {
	Event string
	Data  interface{}
}

var defaultStore *appStore
var allowedOrigins []string

type contextKey string

const currentUserContextKey contextKey = "aiterm_current_user"

func NewRouter(cfg config.Config) (http.Handler, error) {
	store, err := newAppStore(cfg)
	if err != nil {
		return nil, err
	}

	defaultStore = store
	allowedOrigins = append([]string(nil), cfg.CORS.AllowedOrigins...)
	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/api/conversations", handleConversations)
	mux.HandleFunc("/api/conversations/stream", handleConversationStream)
	mux.HandleFunc("/api/conversations/", handleConversationDetail)
	mux.HandleFunc("/api/tasks", handleTasks)
	mux.HandleFunc("/api/tasks/", handleTaskDetail)
	mux.HandleFunc("/api/auth/status", handleAuthStatus)
	mux.HandleFunc("/api/auth/login", handleAuthLogin)
	mux.HandleFunc("/api/auth/logout", handleAuthLogout)
	mux.HandleFunc("/api/auth/me", handleAuthMe)
	mux.HandleFunc("/api/auth/change-password", handleAuthChangePassword)
	mux.HandleFunc("/api/settings/llm/public", handleLLMPublicInfo)
	mux.HandleFunc("/api/settings/llm", handleLLMSettings)
	mux.HandleFunc("/api/settings/auth", handleAuthSettings)
	mux.HandleFunc("/api/nodes", handleNodes)
	mux.HandleFunc("/api/nodes/", handleNodeDetail)
	mux.HandleFunc("/api/users", handleUsers)
	mux.HandleFunc("/api/users/", handleUserDetail)
	mux.HandleFunc("/api/terminal/execute", handleTerminalExecute)

	return withCORS(withAuth(loggingMiddleware(cfg.Log)(mux))), nil
}

func handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: map[string]interface{}{
			"status":    "ok",
			"bootstrap": defaultStore.bootstrapStatus(),
		},
	})
}

func handleConversations(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		items := defaultStore.listConversations()
		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data: map[string]interface{}{
				"items": items,
				"total": len(items),
			},
		})
		return
	}

	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	var req conversationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1000,
			Message: "invalid request",
			Data:    nil,
		})
		return
	}

	if strings.TrimSpace(req.Message) == "" {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1001,
			Message: "message is required",
			Data:    nil,
		})
		return
	}

	nodeID := strings.TrimSpace(req.NodeID)
	if nodeID == "" {
		nodeID = defaultLocalNodeID
	}

	mode := normalizeConversationMode(req.Mode)
	if mode == "chat" {
		conversationID, settings, node, history := defaultStore.prepareChatConversation(req.ConversationID, nodeID)
		reply, err := generateChatReply(settings, node, history, req.Message)
		if err != nil {
			reply = fmt.Sprintf(
				"对话模式当前调用模型失败。当前配置地址：%s，模型：%s。错误：%s。请到设置页检查大模型配置。",
				strings.TrimSpace(settings.APIURL),
				strings.TrimSpace(settings.Model),
				err.Error(),
			)
		}

		defaultStore.completeChatConversation(conversationID, req.Message, reply)
		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data: map[string]interface{}{
				"conversation_id": conversationID,
				"reply":           reply,
				"task_id":         "",
				"mode":            mode,
			},
		})
		return
	}

	conversationID, reply, task, mode, err := defaultStore.createConversation(req.ConversationID, nodeID, req.Message, req.Mode)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1004,
			Message: err.Error(),
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: map[string]interface{}{
			"conversation_id": conversationID,
			"reply":           reply,
			"task_id":         taskIDValue(task),
			"mode":            mode,
		},
	})
}

func handleConversationStream(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		writeJSON(w, http.StatusInternalServerError, response{
			Code:    5001,
			Message: "streaming unsupported",
			Data:    nil,
		})
		return
	}

	var req conversationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1000,
			Message: "invalid request",
			Data:    nil,
		})
		return
	}

	if strings.TrimSpace(req.Message) == "" {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1001,
			Message: "message is required",
			Data:    nil,
		})
		return
	}

	if normalizeConversationMode(req.Mode) != "chat" {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1011,
			Message: "streaming is only supported in chat mode",
			Data:    nil,
		})
		return
	}

	nodeID := strings.TrimSpace(req.NodeID)
	if nodeID == "" {
		nodeID = defaultLocalNodeID
	}

	conversationID, settings, node, history := defaultStore.prepareChatConversation(req.ConversationID, nodeID)

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	writeSSEEvent(w, flusher, "conversation.meta", map[string]interface{}{
		"conversation_id": conversationID,
		"mode":            "chat",
		"node_id":         node.ID,
	})

	defaultStore.appendConversationMessage(conversationID, "user", req.Message)

	var replyBuilder strings.Builder
	reply, err := streamChatReply(r.Context(), settings, node, history, req.Message, func(chunk string) error {
		replyBuilder.WriteString(chunk)
		writeSSEEvent(w, flusher, "conversation.delta", map[string]interface{}{
			"conversation_id": conversationID,
			"delta":           chunk,
		})
		return nil
	})
	if err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(r.Context().Err(), context.Canceled) {
			return
		}
		reply = fmt.Sprintf(
			"对话模式当前调用模型失败。当前配置地址：%s，模型：%s。错误：%s。请到设置页检查大模型配置。",
			strings.TrimSpace(settings.APIURL),
			strings.TrimSpace(settings.Model),
			err.Error(),
		)
		if strings.TrimSpace(replyBuilder.String()) == "" {
			writeSSEEvent(w, flusher, "conversation.delta", map[string]interface{}{
				"conversation_id": conversationID,
				"delta":           reply,
			})
		}
	}

	defaultStore.appendConversationMessage(conversationID, "assistant", reply)
	writeSSEEvent(w, flusher, "conversation.done", map[string]interface{}{
		"conversation_id": conversationID,
		"reply":           reply,
	})
}

func handleConversationDetail(w http.ResponseWriter, r *http.Request) {
	conversationPath := strings.TrimPrefix(r.URL.Path, "/api/conversations/")
	if conversationPath == "" {
		writeJSON(w, http.StatusNotFound, response{
			Code:    4041,
			Message: "conversation not found",
			Data:    nil,
		})
		return
	}

	if strings.HasSuffix(conversationPath, "/messages") {
		handleConversationMessages(w, r, strings.TrimSuffix(conversationPath, "/messages"))
		return
	}

	if r.Method == http.MethodDelete {
		if !defaultStore.deleteConversation(conversationPath) {
			writeJSON(w, http.StatusNotFound, response{
				Code:    4041,
				Message: "conversation not found",
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data: map[string]string{
				"conversation_id": conversationPath,
				"status":          "deleted",
			},
		})
		return
	}

	writeJSON(w, http.StatusNotFound, response{
		Code:    4041,
		Message: "conversation not found",
		Data:    nil,
	})
}

func handleConversationMessages(w http.ResponseWriter, r *http.Request, conversationID string) {
	if r.Method != http.MethodGet {
		writeMethodNotAllowed(w)
		return
	}

	items, ok := defaultStore.listConversationMessages(conversationID)
	if !ok {
		writeJSON(w, http.StatusNotFound, response{
			Code:    4041,
			Message: "conversation not found",
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: map[string]interface{}{
			"conversation_id": conversationID,
			"items":           items,
			"latest_task_id":  defaultStore.getLatestTaskID(conversationID),
		},
	})
}

func handleTasks(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeMethodNotAllowed(w)
		return
	}

	items := defaultStore.listTasks()
	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: map[string]interface{}{
			"items":     items,
			"total":     len(items),
			"page":      1,
			"page_size": 20,
		},
	})
}

func handleTaskDetail(w http.ResponseWriter, r *http.Request) {
	taskID := strings.TrimPrefix(r.URL.Path, "/api/tasks/")
	if taskID == "" {
		writeJSON(w, http.StatusNotFound, response{
			Code:    4040,
			Message: "task not found",
			Data:    nil,
		})
		return
	}

	if strings.HasSuffix(taskID, "/events") {
		handleTaskEvents(w, r, strings.TrimSuffix(taskID, "/events"))
		return
	}

	if strings.HasSuffix(taskID, "/confirm") {
		handleTaskConfirm(w, r, strings.TrimSuffix(taskID, "/confirm"))
		return
	}

	if strings.HasSuffix(taskID, "/stop") {
		handleTaskStop(w, r, strings.TrimSuffix(taskID, "/stop"))
		return
	}

	if strings.HasSuffix(taskID, "/restart") {
		handleTaskRestart(w, r, strings.TrimSuffix(taskID, "/restart"))
		return
	}

	if r.Method == http.MethodDelete {
		if !defaultStore.deleteTask(taskID) {
			writeJSON(w, http.StatusNotFound, response{
				Code:    4040,
				Message: "task not found",
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data: map[string]string{
				"task_id": taskID,
				"status":  "deleted",
			},
		})
		return
	}

	if r.Method != http.MethodGet {
		writeMethodNotAllowed(w)
		return
	}

	task, ok := defaultStore.getTask(taskID)
	if !ok {
		writeJSON(w, http.StatusNotFound, response{
			Code:    4040,
			Message: "task not found",
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data:    task,
	})
}

func handleLLMSettings(w http.ResponseWriter, r *http.Request) {
	if !ensureAdminAccess(w, r) {
		return
	}

	switch r.Method {
	case http.MethodGet:
		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data:    defaultStore.getSettings(),
		})
	case http.MethodPut:
		var settings llmSettings
		if err := json.NewDecoder(r.Body).Decode(&settings); err != nil {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1000,
				Message: "invalid request",
				Data:    nil,
			})
			return
		}

		if strings.TrimSpace(settings.APIURL) == "" || strings.TrimSpace(settings.Model) == "" {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1002,
				Message: "api_url and model are required",
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data:    defaultStore.saveSettings(settings),
		})
	default:
		writeMethodNotAllowed(w)
	}
}

func handleLLMPublicInfo(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeMethodNotAllowed(w)
		return
	}

	settings := defaultStore.getSettings()
	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: llmPublicInfo{
			Model:      strings.TrimSpace(settings.Model),
			Configured: settings.Configured,
		},
	})
}

func handleAuthSettings(w http.ResponseWriter, r *http.Request) {
	if !ensureAdminAccess(w, r) {
		return
	}

	switch r.Method {
	case http.MethodGet:
		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data:    defaultStore.getAuthSettings(),
		})
	case http.MethodPut:
		var settings authSettings
		if err := json.NewDecoder(r.Body).Decode(&settings); err != nil {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1000,
				Message: "invalid request",
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data:    defaultStore.saveAuthSettings(settings),
		})
	default:
		writeMethodNotAllowed(w)
	}
}

func handleAuthStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeMethodNotAllowed(w)
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data:    defaultStore.getAuthStatus(readBearerToken(r)),
	})
}

func handleAuthLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	var req authLoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1000,
			Message: "invalid request",
			Data:    nil,
		})
		return
	}

	data, err := defaultStore.login(req.Username, req.Password)
	if err != nil {
		writeJSON(w, http.StatusUnauthorized, response{
			Code:    4010,
			Message: err.Error(),
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data:    data,
	})
}

func handleAuthLogout(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	defaultStore.logout(readBearerToken(r))
	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: map[string]string{
			"status": "logged_out",
		},
	})
}

func handleAuthMe(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeMethodNotAllowed(w)
		return
	}

	user, ok := currentUserFromContext(r.Context())
	if !ok {
		writeJSON(w, http.StatusUnauthorized, response{
			Code:    4011,
			Message: "unauthorized",
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data:    user,
	})
}

func handleAuthChangePassword(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	user, ok := currentUserFromContext(r.Context())
	if !ok {
		writeJSON(w, http.StatusUnauthorized, response{
			Code:    4011,
			Message: "unauthorized",
			Data:    nil,
		})
		return
	}

	var req authChangePasswordRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1000,
			Message: "invalid request",
			Data:    nil,
		})
		return
	}

	if err := defaultStore.changePassword(user.ID, req.CurrentPassword, req.NewPassword); err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1009,
			Message: err.Error(),
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: map[string]interface{}{
			"status":          "password_changed",
			"reauth_required": true,
		},
	})
}

func handleTaskConfirm(w http.ResponseWriter, r *http.Request, taskID string) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	var req taskConfirmRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1000,
			Message: "invalid request",
			Data:    nil,
		})
		return
	}

	task, err := defaultStore.confirmTask(taskID, req.Approved)
	if err != nil {
		status := http.StatusBadRequest
		code := 1005
		if err.Error() == "task not found" {
			status = http.StatusNotFound
			code = 4040
		}

		writeJSON(w, status, response{
			Code:    code,
			Message: err.Error(),
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data:    task,
	})
}

func handleTaskStop(w http.ResponseWriter, r *http.Request, taskID string) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	task, err := defaultStore.stopTask(taskID)
	if err != nil {
		status := http.StatusBadRequest
		code := 1005
		if err.Error() == "task not found" {
			status = http.StatusNotFound
			code = 4040
		}

		writeJSON(w, status, response{
			Code:    code,
			Message: err.Error(),
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data:    task,
	})
}

func handleTaskRestart(w http.ResponseWriter, r *http.Request, taskID string) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	task, err := defaultStore.restartTask(taskID)
	if err != nil {
		status := http.StatusBadRequest
		code := 1005
		if err.Error() == "task not found" {
			status = http.StatusNotFound
			code = 4040
		}

		writeJSON(w, status, response{
			Code:    code,
			Message: err.Error(),
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data:    task,
	})
}

func handleNodes(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data: map[string]interface{}{
				"items": defaultStore.listNodes(),
			},
		})
	case http.MethodPost:
		if !ensureAdminAccess(w, r) {
			return
		}

		var req nodeRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1000,
				Message: "invalid request",
				Data:    nil,
			})
			return
		}

		if strings.TrimSpace(req.Name) == "" || strings.TrimSpace(req.Host) == "" {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1003,
				Message: "name and host are required",
				Data:    nil,
			})
			return
		}

		if req.Port <= 0 {
			req.Port = 22
		}

		node := defaultStore.createNode(req.Name, req.Host, req.Port)
		writeJSON(w, http.StatusCreated, response{
			Code:    0,
			Message: "ok",
			Data:    node,
		})
	default:
		writeMethodNotAllowed(w)
	}
}

func handleNodeDetail(w http.ResponseWriter, r *http.Request) {
	nodePath := strings.TrimPrefix(r.URL.Path, "/api/nodes/")
	if nodePath == "" {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1000,
			Message: "node id is required",
			Data:    nil,
		})
		return
	}

	nodeID := nodePath

	switch r.Method {
	case http.MethodPut:
		if !ensureAdminAccess(w, r) {
			return
		}

		var req nodeRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1000,
				Message: "invalid request",
				Data:    nil,
			})
			return
		}

		if strings.TrimSpace(req.Name) == "" || strings.TrimSpace(req.Host) == "" {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1003,
				Message: "name and host are required",
				Data:    nil,
			})
			return
		}

		if req.Port <= 0 {
			req.Port = 22
		}

		node, ok := defaultStore.updateNode(nodeID, req.Name, req.Host, req.Port)
		if !ok {
			writeJSON(w, http.StatusNotFound, response{
				Code:    1004,
				Message: "node not found",
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data:    node,
		})
	case http.MethodDelete:
		if !ensureAdminAccess(w, r) {
			return
		}

		if !defaultStore.deleteNode(nodeID) {
			writeJSON(w, http.StatusNotFound, response{
				Code:    1004,
				Message: "node not found",
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data:    nil,
		})
	default:
		writeMethodNotAllowed(w)
	}
}

func handleUsers(w http.ResponseWriter, r *http.Request) {
	if !ensureAdminAccess(w, r) {
		return
	}

	switch r.Method {
	case http.MethodGet:
		items := defaultStore.listUsers()
		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data: map[string]interface{}{
				"items": items,
				"total": len(items),
			},
		})
	case http.MethodPost:
		var req userRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1000,
				Message: "invalid request",
				Data:    nil,
			})
			return
		}

		user, err := defaultStore.createUser(req)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1006,
				Message: err.Error(),
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusCreated, response{
			Code:    0,
			Message: "ok",
			Data:    user,
		})
	default:
		writeMethodNotAllowed(w)
	}
}

func handleUserDetail(w http.ResponseWriter, r *http.Request) {
	if !ensureAdminAccess(w, r) {
		return
	}

	userPath := strings.TrimPrefix(r.URL.Path, "/api/users/")
	if userPath == "" {
		writeJSON(w, http.StatusNotFound, response{
			Code:    4042,
			Message: "user not found",
			Data:    nil,
		})
		return
	}

	if strings.HasSuffix(userPath, "/reset-password") {
		handleUserResetPassword(w, r, strings.TrimSuffix(userPath, "/reset-password"))
		return
	}

	userID := userPath

	currentUser, _ := currentUserFromContext(r.Context())

	switch r.Method {
	case http.MethodPut:
		var req userUpdateRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, response{
				Code:    1000,
				Message: "invalid request",
				Data:    nil,
			})
			return
		}

		user, err := defaultStore.updateUser(userID, req, currentUser.ID)
		if err != nil {
			status := http.StatusBadRequest
			code := 1007
			if err.Error() == "user not found" {
				status = http.StatusNotFound
				code = 4042
			}

			writeJSON(w, status, response{
				Code:    code,
				Message: err.Error(),
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data:    user,
		})
	case http.MethodDelete:
		if err := defaultStore.deleteUser(userID, currentUser.ID); err != nil {
			status := http.StatusBadRequest
			code := 1008
			if err.Error() == "user not found" {
				status = http.StatusNotFound
				code = 4042
			}

			writeJSON(w, status, response{
				Code:    code,
				Message: err.Error(),
				Data:    nil,
			})
			return
		}

		writeJSON(w, http.StatusOK, response{
			Code:    0,
			Message: "ok",
			Data: map[string]string{
				"user_id": userID,
				"status":  "deleted",
			},
		})
	default:
		writeMethodNotAllowed(w)
	}
}

func handleUserResetPassword(w http.ResponseWriter, r *http.Request, userID string) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	var req userResetPasswordRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1000,
			Message: "invalid request",
			Data:    nil,
		})
		return
	}

	if err := defaultStore.resetUserPassword(userID, req.Password); err != nil {
		status := http.StatusBadRequest
		code := 1010
		if err.Error() == "user not found" {
			status = http.StatusNotFound
			code = 4042
		}

		writeJSON(w, status, response{
			Code:    code,
			Message: err.Error(),
			Data:    nil,
		})
		return
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: map[string]interface{}{
			"user_id":         userID,
			"status":          "password_reset",
			"reauth_required": true,
		},
	})
}

func handleTaskEvents(w http.ResponseWriter, r *http.Request, taskID string) {
	if r.Method != http.MethodGet {
		writeMethodNotAllowed(w)
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		writeJSON(w, http.StatusInternalServerError, response{
			Code:    5001,
			Message: "streaming unsupported",
			Data:    nil,
		})
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	events, ok := defaultStore.streamTask(taskID)
	if !ok {
		writeJSON(w, http.StatusNotFound, response{
			Code:    4040,
			Message: "task not found",
			Data:    nil,
		})
		return
	}

	for event := range events {
		writeSSEEvent(w, flusher, event.Event, event.Data)
	}
}

func writeSSEEvent(w http.ResponseWriter, flusher http.Flusher, eventName string, data interface{}) {
	raw, err := json.Marshal(data)
	if err != nil {
		return
	}

	_, _ = fmt.Fprintf(w, "event: %s\n", eventName)
	_, _ = fmt.Fprintf(w, "data: %s\n\n", string(raw))
	flusher.Flush()
}

func writeMethodNotAllowed(w http.ResponseWriter) {
	writeJSON(w, http.StatusMethodNotAllowed, response{
		Code:    4050,
		Message: "method not allowed",
		Data:    nil,
	})
}

func writeJSON(w http.ResponseWriter, status int, payload response) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := strings.TrimSpace(r.Header.Get("Origin"))
		if isAllowedOrigin(origin) {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.Header().Set("Vary", "Origin")
		}

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func withAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if isPublicPath(r.URL.Path) {
			next.ServeHTTP(w, r)
			return
		}

		settings := defaultStore.getAuthSettings()
		if !settings.Enabled {
			next.ServeHTTP(w, r)
			return
		}

		user, ok := defaultStore.getUserByToken(readBearerToken(r))
		if !ok {
			writeJSON(w, http.StatusUnauthorized, response{
				Code:    4011,
				Message: "unauthorized",
				Data:    nil,
			})
			return
		}

		ctx := context.WithValue(r.Context(), currentUserContextKey, user)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func readBearerToken(r *http.Request) string {
	raw := strings.TrimSpace(r.Header.Get("Authorization"))
	if raw != "" {
		if !strings.HasPrefix(strings.ToLower(raw), "bearer ") {
			return ""
		}
		return strings.TrimSpace(raw[7:])
	}

	return strings.TrimSpace(r.URL.Query().Get("access_token"))
}

func isPublicPath(path string) bool {
	switch path {
	case "/health", "/api/auth/status", "/api/auth/login":
		return true
	default:
		return false
	}
}

func currentUserFromContext(ctx context.Context) (userItem, bool) {
	value := ctx.Value(currentUserContextKey)
	user, ok := value.(userItem)
	return user, ok
}

func ensureAdminAccess(w http.ResponseWriter, r *http.Request) bool {
	settings := defaultStore.getAuthSettings()
	if !settings.Enabled {
		return true
	}

	user, ok := currentUserFromContext(r.Context())
	if !ok {
		writeJSON(w, http.StatusUnauthorized, response{
			Code:    4011,
			Message: "unauthorized",
			Data:    nil,
		})
		return false
	}

	if user.Role != "admin" {
		writeJSON(w, http.StatusForbidden, response{
			Code:    4030,
			Message: "admin access required",
			Data:    nil,
		})
		return false
	}

	return true
}

func taskIDValue(task *taskItem) string {
	if task == nil {
		return ""
	}

	return task.ID
}

func isAllowedOrigin(origin string) bool {
	if origin == "" {
		return false
	}

	for _, allowedOrigin := range allowedOrigins {
		if origin == allowedOrigin {
			return true
		}
	}

	return false
}
