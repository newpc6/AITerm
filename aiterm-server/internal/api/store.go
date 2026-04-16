package api

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"aiterm-server/internal/config"
)

type appStore struct {
	mu                      sync.Mutex
	defaultChatPrompt       string
	defaultTaskPrompt       string
	defaultTaskUserPrompt   string
	defaultWindowsToolPrompt string
	defaultLinuxToolPrompt   string
	defaultMacToolPrompt     string
	defaultTaskRepairPrompt string
	defaultTaskRulesPrompt  string
	defaultCommandBlacklist []string
	defaultCommandWhitelist []string
	conversationCounter     int
	taskCounter             int
	nodeCounter             int
	messageCounter          int
	userCounter             int
	sessionCounter          int
	tasks                   map[string]taskItem
	taskOrder               []string
	nodes                   map[string]nodeItem
	nodeOrder               []string
	conversationMessages    map[string][]conversationMessageItem
	settings                llmSettings
	authSettings            authSettings
	users                   map[string]userItem
	userOrder               []string
	sessions                map[string]sessionItem
	taskCancels             map[string]context.CancelFunc
	stoppedTasks            map[string]bool
	sqlite                  *sqlitePersistence
	mysql                   *mysqlPersistence
}

const defaultLocalNodeID = "1"

func newAppStore(cfg config.Config) (*appStore, error) {
	store := &appStore{
		defaultChatPrompt:       strings.TrimSpace(cfg.LLM.ChatSystemPrompt),
		defaultTaskPrompt:       strings.TrimSpace(cfg.LLM.TaskPlannerPrompt),
		defaultTaskUserPrompt:   strings.TrimSpace(cfg.LLM.TaskPlannerUserPrompt),
		defaultWindowsToolPrompt: strings.TrimSpace(cfg.LLM.TaskWindowsToolPrompt),
		defaultLinuxToolPrompt:   strings.TrimSpace(cfg.LLM.TaskLinuxToolPrompt),
		defaultMacToolPrompt:     strings.TrimSpace(cfg.LLM.TaskMacToolPrompt),
		defaultTaskRepairPrompt: strings.TrimSpace(cfg.LLM.TaskFailureRepairPrompt),
		defaultTaskRulesPrompt:  strings.TrimSpace(cfg.LLM.TaskCommandRulesPrompt),
		defaultCommandBlacklist: normalizeCommandRules(cfg.LLM.TaskCommandBlacklist),
		defaultCommandWhitelist: normalizeCommandRules(cfg.LLM.TaskCommandWhitelist),
		conversationCounter:     1,
		taskCounter:             1,
		nodeCounter:             1,
		messageCounter:          1,
		userCounter:             1,
		sessionCounter:          1,
		tasks:                   make(map[string]taskItem),
		taskOrder:               make([]string, 0),
		nodes: map[string]nodeItem{
			defaultLocalNodeID: {
				ID:     defaultLocalNodeID,
				Name:   "local",
				Host:   "127.0.0.1",
				Port:   22,
				Status: "online",
			},
		},
		nodeOrder: []string{defaultLocalNodeID},
		settings: llmSettings{
			APIURL:                  "https://api.openai.com/v1",
			APIKey:                  "",
			Model:                   "gpt-4o-mini",
			Temperature:             0.7,
			ChatSystemPrompt:        strings.TrimSpace(cfg.LLM.ChatSystemPrompt),
			TaskPlannerPrompt:       strings.TrimSpace(cfg.LLM.TaskPlannerPrompt),
			TaskPlannerUserPrompt:   strings.TrimSpace(cfg.LLM.TaskPlannerUserPrompt),
			TaskWindowsToolPrompt:   strings.TrimSpace(cfg.LLM.TaskWindowsToolPrompt),
			TaskLinuxToolPrompt:     strings.TrimSpace(cfg.LLM.TaskLinuxToolPrompt),
			TaskMacToolPrompt:       strings.TrimSpace(cfg.LLM.TaskMacToolPrompt),
			TaskFailureRepairPrompt: strings.TrimSpace(cfg.LLM.TaskFailureRepairPrompt),
			TaskCommandRulesPrompt:  strings.TrimSpace(cfg.LLM.TaskCommandRulesPrompt),
			TaskCommandBlacklist:    normalizeCommandRules(cfg.LLM.TaskCommandBlacklist),
			TaskCommandWhitelist:    normalizeCommandRules(cfg.LLM.TaskCommandWhitelist),
			Configured:              false,
		},
		authSettings: authSettings{
			Enabled:            false,
			AllowPasswordLogin: true,
			SessionTTLHours:    24,
		},
		conversationMessages: make(map[string][]conversationMessageItem),
		users:                make(map[string]userItem),
		userOrder:            make([]string, 0),
		sessions:             make(map[string]sessionItem),
		taskCancels:          make(map[string]context.CancelFunc),
		stoppedTasks:         make(map[string]bool),
	}

	switch strings.ToLower(strings.TrimSpace(cfg.Database.Driver)) {
	case "", "sqlite":
		sqliteStore, err := newSQLitePersistence(cfg.Database.SQLitePath)
		if err != nil {
			return nil, err
		}
		store.sqlite = sqliteStore
		store.loadFromSQLite()
	case "mysql":
		mysqlStore, err := newMySQLPersistence(cfg.Database.MySQLDSN)
		if err != nil {
			return nil, err
		}
		store.mysql = mysqlStore
		store.loadFromMySQL()
	default:
		return nil, fmt.Errorf("unsupported database driver: %s", cfg.Database.Driver)
	}

	store.applySettingsDefaults()

	if len(store.taskOrder) == 0 {
		seed := store.newTask("1", store.nodes[defaultLocalNodeID], "Install nginx on the local machine")
		seed.Status = "executing"
		seed.Progress = 30
		seed.Steps[0].Status = "completed"
		seed.Steps[1].Status = "executing"
		store.tasks[seed.ID] = seed
		store.taskOrder = append(store.taskOrder, seed.ID)
	}
	store.ensureBootstrapDataLocked()

	store.recalculateCountersLocked()
	store.persistAllLocked()

	return store, nil
}

func (s *appStore) createConversation(conversationID, nodeID, message, mode string) (string, string, *taskItem, string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if strings.TrimSpace(conversationID) == "" {
		conversationID = nextNumericID(&s.conversationCounter)
	}

	mode = normalizeConversationMode(mode)
	if mode == "chat" {
		reply := s.buildChatReply(message)
		s.appendConversationMessageLocked(conversationID, "user", message)
		s.appendConversationMessageLocked(conversationID, "assistant", reply)
		s.persistAllLocked()
		return conversationID, reply, nil, mode, nil
	}

	node, ok := s.nodes[nodeID]
	if !ok {
		return "", "", nil, "", fmt.Errorf("node not found")
	}
	task := s.newTask(conversationID, node, message)
	s.tasks[task.ID] = task
	s.taskOrder = append(s.taskOrder, task.ID)

	reply := fmt.Sprintf("已收到发往节点 %s 的任务：%s", node.Name, message)
	s.appendConversationMessageLocked(conversationID, "user", message)
	s.appendConversationMessageLocked(conversationID, "assistant", reply)
	s.persistAllLocked()

	clonedTask := cloneTask(task)
	return conversationID, reply, &clonedTask, mode, nil
}

func (s *appStore) prepareChatConversation(conversationID, nodeID string) (string, llmSettings, nodeItem, []conversationMessageItem) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if strings.TrimSpace(conversationID) == "" {
		conversationID = nextNumericID(&s.conversationCounter)
	}

	node, ok := s.nodes[nodeID]
	if !ok {
		node = s.nodes[defaultLocalNodeID]
	}

	history := append([]conversationMessageItem(nil), s.conversationMessages[conversationID]...)
	return conversationID, s.settings, node, history
}

func (s *appStore) completeChatConversation(conversationID, message, reply string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.appendConversationMessageLocked(conversationID, "user", message)
	s.appendConversationMessageLocked(conversationID, "assistant", reply)
	s.persistAllLocked()
}

func (s *appStore) newTask(conversationID string, node nodeItem, message string) taskItem {
	now := time.Now().UTC().Format(time.RFC3339)
	taskID := nextNumericID(&s.taskCounter)
	nodeLabel := describeNode(node)

	return taskItem{
		ID:             taskID,
		Title:          buildTaskTitle(message, node),
		Status:         "pending",
		Progress:       0,
		ConversationID: conversationID,
		NodeID:         node.ID,
		Request:        strings.TrimSpace(message),
		PendingCommand: "",
		RiskReason:     "",
		Summary:        fmt.Sprintf("任务已创建，等待模型基于节点 %s 生成执行计划。", nodeLabel),
		Steps:          nil,
		CreatedAt:      now,
		UpdatedAt:      now,
	}
}

func (s *appStore) listTasks() []taskItem {
	s.mu.Lock()
	defer s.mu.Unlock()

	items := make([]taskItem, 0, len(s.taskOrder))
	for i := len(s.taskOrder) - 1; i >= 0; i-- {
		taskID := s.taskOrder[i]
		task, ok := s.tasks[taskID]
		if ok {
			items = append(items, cloneTask(task))
		}
	}

	return items
}

func (s *appStore) listUsers() []userItem {
	s.mu.Lock()
	defer s.mu.Unlock()

	items := make([]userItem, 0, len(s.userOrder))
	for _, userID := range s.userOrder {
		user, ok := s.users[userID]
		if ok {
			items = append(items, sanitizeUser(user))
		}
	}

	return items
}

func (s *appStore) getUserByToken(token string) (userItem, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	return s.getUserByTokenLocked(token)
}

func (s *appStore) listConversationMessages(conversationID string) ([]conversationMessageItem, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	items, ok := s.conversationMessages[conversationID]
	if !ok {
		return nil, false
	}

	cloned := make([]conversationMessageItem, len(items))
	copy(cloned, items)
	return cloned, true
}

func (s *appStore) deleteConversation(conversationID string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	_, hasMessages := s.conversationMessages[conversationID]
	hasTask := false
	for _, taskID := range s.taskOrder {
		task, ok := s.tasks[taskID]
		if ok && task.ConversationID == conversationID {
			hasTask = true
			break
		}
	}

	if !hasMessages && !hasTask {
		return false
	}

	delete(s.conversationMessages, conversationID)

	nextTaskOrder := make([]string, 0, len(s.taskOrder))
	for _, taskID := range s.taskOrder {
		task, ok := s.tasks[taskID]
		if !ok {
			continue
		}
		if task.ConversationID == conversationID {
			delete(s.tasks, taskID)
			continue
		}
		nextTaskOrder = append(nextTaskOrder, taskID)
	}
	s.taskOrder = nextTaskOrder

	s.persistAllLocked()
	return true
}

func (s *appStore) deleteTask(taskID string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, ok := s.tasks[taskID]
	if !ok {
		return false
	}

	if cancel, exists := s.taskCancels[taskID]; exists {
		cancel()
		delete(s.taskCancels, taskID)
	}
	delete(s.stoppedTasks, taskID)
	delete(s.tasks, taskID)
	s.taskOrder = removeString(s.taskOrder, taskID)

	if latestTask, exists := s.getLatestTaskByConversationLocked(task.ConversationID); !exists || latestTask.ID != taskID {
		s.persistAllLocked()
		return true
	}

	s.persistAllLocked()
	return true
}

func (s *appStore) listConversations() []conversationListItem {
	s.mu.Lock()
	defer s.mu.Unlock()

	items := make([]conversationListItem, 0, len(s.conversationMessages))
	for conversationID, messages := range s.conversationMessages {
		if len(messages) == 0 {
			continue
		}

		lastMessage := messages[len(messages)-1]
		title := buildConversationTitle(messages)
		latestTask, hasTask := s.getLatestTaskByConversationLocked(conversationID)

		item := conversationListItem{
			ID:           conversationID,
			Title:        title,
			LastMessage:  buildConversationExcerpt(lastMessage.Content),
			MessageCount: len(messages),
			UpdatedAt:    lastMessage.CreatedAt,
		}

		if hasTask {
			item.LatestTaskID = latestTask.ID
			item.LatestNodeID = latestTask.NodeID
			item.LatestStatus = latestTask.Status
			item.UpdatedAt = latestTask.UpdatedAt
		}

		items = append(items, item)
	}

	sortConversationItems(items)
	return items
}

func (s *appStore) getLatestTaskID(conversationID string) string {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, ok := s.getLatestTaskByConversationLocked(conversationID)
	if !ok {
		return ""
	}

	return task.ID
}

func (s *appStore) getTask(taskID string) (taskItem, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, ok := s.tasks[taskID]
	if !ok {
		return taskItem{}, false
	}

	return cloneTask(task), true
}

func (s *appStore) getAuthSettings() authSettings {
	s.mu.Lock()
	defer s.mu.Unlock()

	return s.authSettings
}

func (s *appStore) bootstrapStatus() map[string]interface{} {
	s.mu.Lock()
	defer s.mu.Unlock()

	return map[string]interface{}{
		"nodes_ready":        len(s.nodeOrder) > 0,
		"active_admin_count": s.activeAdminCountLocked(),
		"default_username":   "admin",
	}
}

func (s *appStore) getAuthStatus(token string) authStatusData {
	s.mu.Lock()
	defer s.mu.Unlock()

	status := authStatusData{
		Enabled:            s.authSettings.Enabled,
		AllowPasswordLogin: s.authSettings.AllowPasswordLogin,
		Authenticated:      false,
	}

	user, ok := s.getUserByTokenLocked(token)
	if ok {
		sanitized := sanitizeUser(user)
		status.Authenticated = true
		status.User = &sanitized
	}

	return status
}

func (s *appStore) saveAuthSettings(settings authSettings) authSettings {
	s.mu.Lock()
	defer s.mu.Unlock()

	if settings.SessionTTLHours <= 0 {
		settings.SessionTTLHours = 24
	}
	s.authSettings = settings
	s.persistAllLocked()
	return s.authSettings
}

func (s *appStore) login(username, password string) (authLoginData, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.authSettings.AllowPasswordLogin {
		return authLoginData{}, fmt.Errorf("password login is disabled")
	}

	normalizedUsername := strings.ToLower(strings.TrimSpace(username))
	passwordHash := hashPassword(password)

	var user userItem
	found := false
	for _, userID := range s.userOrder {
		existing, ok := s.users[userID]
		if ok && existing.Username == normalizedUsername {
			user = existing
			found = true
			break
		}
	}

	if !found || user.PasswordHash != passwordHash {
		return authLoginData{}, fmt.Errorf("invalid username or password")
	}

	if user.Status != "active" {
		return authLoginData{}, fmt.Errorf("user is disabled")
	}

	now := time.Now().UTC()
	user.LastLoginAt = now.Format(time.RFC3339)
	user.UpdatedAt = user.LastLoginAt
	s.users[user.ID] = user

	token := generateSessionToken()
	session := sessionItem{
		ID:        nextNumericID(&s.sessionCounter),
		Token:     token,
		UserID:    user.ID,
		CreatedAt: now.Format(time.RFC3339),
		ExpiresAt: now.Add(time.Duration(s.authSettings.SessionTTLHours) * time.Hour).Format(time.RFC3339),
	}
	s.sessions[token] = session
	s.persistAllLocked()

	return authLoginData{
		Token:     token,
		ExpiresAt: session.ExpiresAt,
		User:      sanitizeUser(user),
	}, nil
}

func (s *appStore) logout(token string) {
	if strings.TrimSpace(token) == "" {
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	delete(s.sessions, token)
	s.persistAllLocked()
}

func (s *appStore) streamTask(taskID string) (<-chan sseEvent, bool) {
	s.mu.Lock()
	task, ok := s.tasks[taskID]
	if !ok {
		s.mu.Unlock()
		return nil, false
	}

	if task.Status == "waiting_confirm" {
		s.mu.Unlock()
		confirmationMessage := "当前任务等待人工确认后执行。"
		if strings.TrimSpace(task.PendingCommand) != "" {
			confirmationMessage = fmt.Sprintf("当前任务等待人工确认后执行：\n%s", task.PendingCommand)
		}
		return buildClosedEventStream(
			sseEvent{
				Event: "task.status",
				Data: map[string]interface{}{
					"task_id":  task.ID,
					"status":   task.Status,
					"progress": task.Progress,
				},
			},
			sseEvent{
				Event: "task.output",
				Data: map[string]interface{}{
					"task_id": task.ID,
					"stream":  "stdout",
					"content": confirmationMessage,
				},
			},
		), true
	}

	if task.Status == "cancelled" || task.Status == "completed" || task.Status == "failed" {
		s.mu.Unlock()
		return buildClosedEventStream(
			sseEvent{
				Event: "task.status",
				Data: map[string]interface{}{
					"task_id":  task.ID,
					"status":   task.Status,
					"progress": task.Progress,
				},
			},
		), true
	}

	if _, running := s.taskCancels[taskID]; running {
		s.mu.Unlock()
		return buildClosedEventStream(buildTaskStatusEvent(task)), true
	}

	skipPlanning := task.Status == "pending" && isTaskPlanned(task)
	if skipPlanning {
		task.Status = "executing"
		task.Progress = max(task.Progress, 55)
		task.Summary = "命令已确认，正在通过真实执行器运行。"
		for index := range task.Steps {
			if task.Steps[index].Status == "waiting_confirm" {
				task.Steps[index].Status = "pending"
			}
		}
	} else {
		task.Status = "analyzing"
		task.Progress = 20
		task.Summary = "正在分析任务并生成执行计划。"
	}
	task.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	s.tasks[task.ID] = task
	s.persistAllLocked()
	s.mu.Unlock()

	ctx, cancel := context.WithCancel(context.Background())
	if !s.registerTaskExecution(task.ID, cancel) {
		cancel()
		return buildClosedEventStream(buildTaskStatusEvent(task)), true
	}

	stream := make(chan sseEvent, 32)
	go s.runTaskExecution(ctx, task.ID, skipPlanning, stream)
	return stream, true
}

func (s *appStore) confirmTask(taskID string, approved bool) (taskItem, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, ok := s.tasks[taskID]
	if !ok {
		return taskItem{}, fmt.Errorf("task not found")
	}

	if task.Status != "waiting_confirm" {
		return taskItem{}, fmt.Errorf("task does not require confirmation")
	}

	task.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	if approved {
		delete(s.stoppedTasks, task.ID)
		task.Status = "pending"
		task.Progress = max(task.Progress, 45)
		task.Summary = "命令已确认，等待执行流启动。"
		for index := range task.Steps {
			if task.Steps[index].Status == "waiting_confirm" {
				task.Steps[index].Status = "pending"
			}
		}
		s.appendConversationMessageLocked(task.ConversationID, "assistant", fmt.Sprintf("任务 %s 已批准，准备开始执行。", task.ID))
	} else {
		task.Status = "cancelled"
		task.Progress = 100
		task.Summary = "任务已取消，待确认命令未执行。"
		for index := range task.Steps {
			if task.Steps[index].Status == "waiting_confirm" || task.Steps[index].Status == "pending" {
				task.Steps[index].Status = "cancelled"
			}
		}
		s.appendConversationMessageLocked(task.ConversationID, "assistant", fmt.Sprintf("任务 %s 已取消，命令未执行。", task.ID))
	}

	s.tasks[task.ID] = task
	s.persistAllLocked()
	return cloneTask(task), nil
}

func (s *appStore) stopTask(taskID string) (taskItem, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, ok := s.tasks[taskID]
	if !ok {
		return taskItem{}, fmt.Errorf("task not found")
	}

	if task.Status == "completed" || task.Status == "failed" || task.Status == "cancelled" {
		return taskItem{}, fmt.Errorf("task cannot be stopped in current status")
	}

	wasWaitingConfirm := task.Status == "waiting_confirm"
	s.stoppedTasks[task.ID] = true
	_, isRunning := s.taskCancels[task.ID]
	if cancel, exists := s.taskCancels[task.ID]; exists {
		cancel()
	}

	task.Status = "cancelled"
	task.Progress = 100
	task.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	task.Summary = "任务已停止。"
	if wasWaitingConfirm || len(task.Steps) == 0 {
		task.Summary = "任务已停止，待执行计划未继续运行。"
	}
	for index := range task.Steps {
		if task.Steps[index].Status != "completed" && task.Steps[index].Status != "failed" {
			task.Steps[index].Status = "cancelled"
		}
	}
	if !isRunning {
		s.appendConversationMessageLocked(task.ConversationID, "assistant", fmt.Sprintf("任务 %s 已停止。", task.ID))
	}
	s.tasks[task.ID] = task
	s.persistAllLocked()
	return cloneTask(task), nil
}

func (s *appStore) restartTask(taskID string) (taskItem, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, ok := s.tasks[taskID]
	if !ok {
		return taskItem{}, fmt.Errorf("task not found")
	}

	if _, running := s.taskCancels[task.ID]; running {
		return taskItem{}, fmt.Errorf("task is running, stop it before restarting")
	}

	switch task.Status {
	case "waiting_confirm", "completed", "failed", "cancelled":
	default:
		return taskItem{}, fmt.Errorf("task cannot be restarted in current status")
	}

	nodeLabel := task.NodeID
	if node, exists := s.nodes[task.NodeID]; exists {
		nodeLabel = describeNode(node)
	}
	delete(s.stoppedTasks, task.ID)
	task.Status = "pending"
	task.Progress = 0
	task.PendingCommand = ""
	task.RiskReason = ""
	task.Summary = fmt.Sprintf("任务已重新启动，等待模型基于节点 %s 生成执行计划。", nodeLabel)
	task.Steps = nil
	task.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	s.appendConversationMessageLocked(task.ConversationID, "assistant", fmt.Sprintf("任务 %s 已重启，将重新生成执行计划。", task.ID))
	s.tasks[task.ID] = task
	s.persistAllLocked()
	return cloneTask(task), nil
}

func (s *appStore) registerTaskExecution(taskID string, cancel context.CancelFunc) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.taskCancels[taskID]; exists {
		return false
	}

	delete(s.stoppedTasks, taskID)
	s.taskCancels[taskID] = cancel
	return true
}

func (s *appStore) finishTaskExecution(taskID string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	delete(s.taskCancels, taskID)
}

func (s *appStore) isTaskStopRequested(taskID string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	return s.stoppedTasks[taskID]
}

func (s *appStore) changePassword(userID, currentPassword, newPassword string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	user, ok := s.users[userID]
	if !ok {
		return fmt.Errorf("user not found")
	}
	if user.PasswordHash != hashPassword(currentPassword) {
		return fmt.Errorf("current password is incorrect")
	}
	if err := validatePassword(newPassword); err != nil {
		return err
	}

	user.PasswordHash = hashPassword(newPassword)
	user.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	s.users[user.ID] = user
	s.deleteSessionsByUserLocked(user.ID)
	s.persistAllLocked()
	return nil
}

func (s *appStore) resetUserPassword(userID, newPassword string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	user, ok := s.users[userID]
	if !ok {
		return fmt.Errorf("user not found")
	}
	if err := validatePassword(newPassword); err != nil {
		return err
	}

	user.PasswordHash = hashPassword(newPassword)
	user.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	s.users[user.ID] = user
	s.deleteSessionsByUserLocked(user.ID)
	s.persistAllLocked()
	return nil
}

func (s *appStore) getSettings() llmSettings {
	s.mu.Lock()
	defer s.mu.Unlock()

	return s.settings
}

func (s *appStore) saveSettings(settings llmSettings) llmSettings {
	s.mu.Lock()
	defer s.mu.Unlock()

	if strings.TrimSpace(settings.ChatSystemPrompt) == "" {
		settings.ChatSystemPrompt = s.defaultChatPrompt
	}
	if strings.TrimSpace(settings.TaskPlannerPrompt) == "" {
		settings.TaskPlannerPrompt = s.defaultTaskPrompt
	}
	if strings.TrimSpace(settings.TaskPlannerUserPrompt) == "" {
		settings.TaskPlannerUserPrompt = s.defaultTaskUserPrompt
	}
	if strings.TrimSpace(settings.TaskWindowsToolPrompt) == "" {
		settings.TaskWindowsToolPrompt = s.defaultWindowsToolPrompt
	}
	if strings.TrimSpace(settings.TaskLinuxToolPrompt) == "" {
		settings.TaskLinuxToolPrompt = s.defaultLinuxToolPrompt
	}
	if strings.TrimSpace(settings.TaskMacToolPrompt) == "" {
		settings.TaskMacToolPrompt = s.defaultMacToolPrompt
	}
	if strings.TrimSpace(settings.TaskFailureRepairPrompt) == "" {
		settings.TaskFailureRepairPrompt = s.defaultTaskRepairPrompt
	}
	if strings.TrimSpace(settings.TaskCommandRulesPrompt) == "" {
		settings.TaskCommandRulesPrompt = s.defaultTaskRulesPrompt
	}
	if settings.TaskCommandBlacklist == nil {
		settings.TaskCommandBlacklist = append([]string(nil), s.defaultCommandBlacklist...)
	}
	if settings.TaskCommandWhitelist == nil {
		settings.TaskCommandWhitelist = append([]string(nil), s.defaultCommandWhitelist...)
	}
	settings.TaskCommandBlacklist = normalizeCommandRules(settings.TaskCommandBlacklist)
	settings.TaskCommandWhitelist = normalizeCommandRules(settings.TaskCommandWhitelist)
	settings.Configured = strings.TrimSpace(settings.APIURL) != "" && strings.TrimSpace(settings.Model) != ""
	s.settings = settings
	s.persistAllLocked()
	return s.settings
}

func (s *appStore) applySettingsDefaults() {
	if strings.TrimSpace(s.defaultChatPrompt) == "" {
		s.defaultChatPrompt = "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。"
	}
	if strings.TrimSpace(s.defaultTaskPrompt) == "" {
		s.defaultTaskPrompt = "你是一个任务规划器，请将用户请求转换为可执行任务计划。"
	}
	if strings.TrimSpace(s.defaultTaskUserPrompt) == "" {
		s.defaultTaskUserPrompt = "请基于以下用户请求生成任务计划，并为每一步提供可直接执行的命令。\n用户请求：{{user_request}}{{conversation_history}}"
	}
	if strings.TrimSpace(s.defaultWindowsToolPrompt) == "" {
		s.defaultWindowsToolPrompt = "当前系统为 Windows。命令优先使用 PowerShell 或系统自带命令，并保证一次执行即可返回结果。"
	}
	if strings.TrimSpace(s.defaultLinuxToolPrompt) == "" {
		s.defaultLinuxToolPrompt = "当前系统为 Linux。命令优先使用通用 shell 命令，并保证一次执行即可返回结果。"
	}
	if strings.TrimSpace(s.defaultMacToolPrompt) == "" {
		s.defaultMacToolPrompt = "当前系统为 macOS。命令优先使用 zsh/bash 兼容命令，并保证一次执行即可返回结果。"
	}
	if strings.TrimSpace(s.defaultTaskRepairPrompt) == "" {
		s.defaultTaskRepairPrompt = "请分析以下自动化任务失败信息，并返回修正结果。任务请求：{{user_request}}\n节点：{{node_description}}\n失败步骤：{{step_title}}\n失败命令：{{failed_command}}\n执行输出：{{execution_output}}\n失败提示：{{failure_text}}"
	}
	if strings.TrimSpace(s.defaultTaskRulesPrompt) == "" {
		s.defaultTaskRulesPrompt = "\n\n命令风控规则：{{command_rules}}"
	}
	if strings.TrimSpace(s.settings.ChatSystemPrompt) == "" {
		s.settings.ChatSystemPrompt = s.defaultChatPrompt
	}
	if strings.TrimSpace(s.settings.TaskPlannerPrompt) == "" {
		s.settings.TaskPlannerPrompt = s.defaultTaskPrompt
	}
	if strings.TrimSpace(s.settings.TaskPlannerUserPrompt) == "" {
		s.settings.TaskPlannerUserPrompt = s.defaultTaskUserPrompt
	}
	if strings.TrimSpace(s.settings.TaskWindowsToolPrompt) == "" {
		s.settings.TaskWindowsToolPrompt = s.defaultWindowsToolPrompt
	}
	if strings.TrimSpace(s.settings.TaskLinuxToolPrompt) == "" {
		s.settings.TaskLinuxToolPrompt = s.defaultLinuxToolPrompt
	}
	if strings.TrimSpace(s.settings.TaskMacToolPrompt) == "" {
		s.settings.TaskMacToolPrompt = s.defaultMacToolPrompt
	}
	if strings.TrimSpace(s.settings.TaskFailureRepairPrompt) == "" {
		s.settings.TaskFailureRepairPrompt = s.defaultTaskRepairPrompt
	}
	if strings.TrimSpace(s.settings.TaskCommandRulesPrompt) == "" {
		s.settings.TaskCommandRulesPrompt = s.defaultTaskRulesPrompt
	}
	if s.defaultCommandBlacklist == nil {
		s.defaultCommandBlacklist = defaultCommandBlacklist()
	}
	if s.defaultCommandWhitelist == nil {
		s.defaultCommandWhitelist = []string{}
	}
	if len(s.settings.TaskCommandBlacklist) == 0 && len(s.defaultCommandBlacklist) > 0 {
		s.settings.TaskCommandBlacklist = append([]string(nil), s.defaultCommandBlacklist...)
	}
	if s.settings.TaskCommandWhitelist == nil {
		s.settings.TaskCommandWhitelist = append([]string(nil), s.defaultCommandWhitelist...)
	}
	s.settings.TaskCommandBlacklist = normalizeCommandRules(s.settings.TaskCommandBlacklist)
	s.settings.TaskCommandWhitelist = normalizeCommandRules(s.settings.TaskCommandWhitelist)
}

func (s *appStore) prepareTaskPlanning(taskID string) (taskItem, llmSettings, nodeItem, []conversationMessageItem, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, ok := s.tasks[taskID]
	if !ok {
		return taskItem{}, llmSettings{}, nodeItem{}, nil, false
	}

	node, ok := s.nodes[task.NodeID]
	if !ok {
		node = s.nodes[defaultLocalNodeID]
	}

	history := append([]conversationMessageItem(nil), s.conversationMessages[task.ConversationID]...)
	return cloneTask(task), s.settings, node, history, true
}

func (s *appStore) getLLMSettings() llmSettings {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.settings
}

func (s *appStore) listNodes() []nodeItem {
	s.mu.Lock()
	defer s.mu.Unlock()

	items := make([]nodeItem, 0, len(s.nodes))
	for _, nodeID := range s.nodeOrder {
		node, ok := s.nodes[nodeID]
		if ok {
			items = append(items, node)
		}
	}

	return items
}

func (s *appStore) getNode(nodeID string) (nodeItem, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	node, ok := s.nodes[nodeID]
	return node, ok
}

func (s *appStore) createNode(name, host string, port int) nodeItem {
	s.mu.Lock()
	defer s.mu.Unlock()

	nodeID := nextNumericID(&s.nodeCounter)

	node := nodeItem{
		ID:     nodeID,
		Name:   strings.TrimSpace(name),
		Host:   strings.TrimSpace(host),
		Port:   port,
		Status: fmt.Sprintf("online:%d", port),
	}
	s.nodes[node.ID] = node
	s.nodeOrder = append(s.nodeOrder, node.ID)
	s.persistAllLocked()

	return node
}

func (s *appStore) updateNode(nodeID string, name, host string, port int) (nodeItem, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	node, ok := s.nodes[nodeID]
	if !ok {
		return nodeItem{}, false
	}

	node.Name = strings.TrimSpace(name)
	node.Host = strings.TrimSpace(host)
	node.Port = port
	node.Status = fmt.Sprintf("online:%d", port)
	s.nodes[nodeID] = node
	s.persistAllLocked()

	return node, true
}

func (s *appStore) deleteNode(nodeID string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, ok := s.nodes[nodeID]; !ok {
		return false
	}

	delete(s.nodes, nodeID)
	for i, id := range s.nodeOrder {
		if id == nodeID {
			s.nodeOrder = append(s.nodeOrder[:i], s.nodeOrder[i+1:]...)
			break
		}
	}
	s.persistAllLocked()

	return true
}

func (s *appStore) createUser(req userRequest) (userItem, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if strings.TrimSpace(req.Username) == "" {
		return userItem{}, fmt.Errorf("username is required")
	}
	if strings.TrimSpace(req.Password) == "" {
		return userItem{}, fmt.Errorf("password is required")
	}
	if err := validatePassword(req.Password); err != nil {
		return userItem{}, err
	}

	normalizedUsername := strings.ToLower(strings.TrimSpace(req.Username))
	for _, existingID := range s.userOrder {
		existing, ok := s.users[existingID]
		if ok && strings.EqualFold(existing.Username, normalizedUsername) {
			return userItem{}, fmt.Errorf("username already exists")
		}
	}

	user := s.newUser(req)
	s.users[user.ID] = user
	s.userOrder = append(s.userOrder, user.ID)
	s.persistAllLocked()

	return sanitizeUser(user), nil
}

func (s *appStore) updateUser(userID string, req userUpdateRequest, actorUserID string) (userItem, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	user, ok := s.users[userID]
	if !ok {
		return userItem{}, fmt.Errorf("user not found")
	}

	nextRole := normalizeUserRole(req.Role, user.Role)
	nextStatus := normalizeUserStatus(req.Status, user.Status)
	nextDisplayName := strings.TrimSpace(req.DisplayName)
	if nextDisplayName == "" {
		nextDisplayName = user.Username
	}

	if user.Role == "admin" && user.Status == "active" && (nextRole != "admin" || nextStatus != "active") && s.activeAdminCountLocked() <= 1 {
		return userItem{}, fmt.Errorf("at least one active admin must remain")
	}

	user.DisplayName = nextDisplayName
	user.Role = nextRole
	user.Status = nextStatus
	user.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	s.users[user.ID] = user

	if user.Status != "active" {
		s.deleteSessionsByUserLocked(user.ID)
	}

	if actorUserID == user.ID && user.Status != "active" {
		s.deleteSessionsByUserLocked(user.ID)
	}

	s.persistAllLocked()
	return sanitizeUser(user), nil
}

func (s *appStore) deleteUser(userID, actorUserID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	user, ok := s.users[userID]
	if !ok {
		return fmt.Errorf("user not found")
	}

	if userID == actorUserID {
		return fmt.Errorf("cannot delete current user")
	}

	if user.Role == "admin" && user.Status == "active" && s.activeAdminCountLocked() <= 1 {
		return fmt.Errorf("at least one active admin must remain")
	}

	delete(s.users, userID)
	s.userOrder = removeString(s.userOrder, userID)
	s.deleteSessionsByUserLocked(userID)
	s.persistAllLocked()
	return nil
}

func buildTaskTitle(message string, node nodeItem) string {
	trimmed := strings.TrimSpace(message)
	if trimmed == "" {
		return fmt.Sprintf("在 %s 上执行任务", node.Name)
	}

	runes := []rune(trimmed)
	if len(runes) <= 32 {
		return fmt.Sprintf("%s | %s", node.Name, trimmed)
	}

	return fmt.Sprintf("%s | %s...", node.Name, string(runes[:32]))
}

func isTaskPlanned(task taskItem) bool {
	return strings.TrimSpace(task.PendingCommand) != "" && len(task.Steps) > 0
}

func buildPendingCommandPreview(steps []taskPlanStep) string {
	lines := make([]string, 0, len(steps))
	for index, step := range steps {
		command := normalizePlannedCommand(step.Command)
		if command == "" {
			continue
		}
		title := strings.TrimSpace(step.Title)
		if title == "" {
			title = fmt.Sprintf("步骤 %d", index+1)
		}
		lines = append(lines, fmt.Sprintf("%d. %s: %s", index+1, title, command))
	}
	return strings.Join(lines, "\n")
}

func buildTaskStepsFromPlan(steps []taskPlanStep) []taskStep {
	items := make([]taskStep, 0, len(steps))
	for index, step := range steps {
		title := strings.TrimSpace(step.Title)
		if title == "" {
			title = fmt.Sprintf("步骤 %d", index+1)
		}
		items = append(items, taskStep{
			Index:   index + 1,
			Title:   title,
			Status:  "pending",
			Command: normalizePlannedCommand(step.Command),
		})
	}
	return items
}

func buildRiskReasonFromPlan(plan taskPlanResult, settings llmSettings) string {
	matchedReason := ""
	for _, step := range plan.Steps {
		if reason := buildRiskReason(step.Command, settings); reason != "" {
			matchedReason = reason
			break
		}
	}

	if matchedReason != "" {
		if plan.RequiresConfirmation && strings.TrimSpace(plan.RiskReason) != "" && !looksLikeBlacklistRiskReason(plan.RiskReason) {
			return strings.TrimSpace(plan.RiskReason)
		}
		return matchedReason
	}

	if plan.RequiresConfirmation {
		if looksLikeBlacklistRiskReason(plan.RiskReason) {
			return ""
		}
		if strings.TrimSpace(plan.RiskReason) != "" {
			return strings.TrimSpace(plan.RiskReason)
		}
		return "模型判定当前任务存在潜在风险，需要人工确认。"
	}

	return ""
}

func describeNode(node nodeItem) string {
	name := strings.TrimSpace(node.Name)
	if name == "" {
		name = "unknown"
	}
	return fmt.Sprintf("%s (%s:%d, %s)", name, strings.TrimSpace(node.Host), node.Port, strings.TrimSpace(node.Status))
}

func buildRiskReason(message string, settings llmSettings) string {
	lower := strings.ToLower(strings.TrimSpace(message))
	if lower == "" {
		return ""
	}

	for _, rule := range normalizeCommandRules(settings.TaskCommandWhitelist) {
		if commandRuleMatches(lower, rule) {
			return ""
		}
	}

	for _, rule := range normalizeCommandRules(settings.TaskCommandBlacklist) {
		if commandRuleMatches(lower, rule) {
			return fmt.Sprintf("命中命令黑名单规则：%s，需要人工确认。", strings.TrimSpace(rule))
		}
	}

	return ""
}

func commandRuleMatches(command string, rule string) bool {
	command = strings.ToLower(strings.TrimSpace(command))
	rule = strings.ToLower(strings.TrimSpace(rule))
	if command == "" || rule == "" {
		return false
	}

	pattern := fmt.Sprintf(`(^|[^a-z0-9_:-])%s([^a-z0-9_:-]|$)`, regexp.QuoteMeta(rule))
	matched, err := regexp.MatchString(pattern, command)
	if err != nil {
		return false
	}
	return matched
}

func looksLikeBlacklistRiskReason(reason string) bool {
	lower := strings.ToLower(strings.TrimSpace(reason))
	if lower == "" {
		return false
	}
	return strings.Contains(lower, "黑名单") || strings.Contains(lower, "命中命令")
}

func normalizeCommandRules(items []string) []string {
	if items == nil {
		return nil
	}

	seen := make(map[string]struct{}, len(items))
	normalized := make([]string, 0, len(items))
	for _, item := range items {
		rule := strings.ToLower(strings.TrimSpace(item))
		if rule == "" {
			continue
		}
		if _, exists := seen[rule]; exists {
			continue
		}
		seen[rule] = struct{}{}
		normalized = append(normalized, rule)
	}
	return normalized
}

var driveLetterPattern = regexp.MustCompile(`(?i)\b([a-z]):`)

func normalizePlannedCommand(command string) string {
	trimmed := strings.TrimSpace(command)
	if trimmed == "" {
		return ""
	}

	lower := strings.ToLower(trimmed)
	if strings.Contains(lower, "wmic logicaldisk") {
		matches := driveLetterPattern.FindStringSubmatch(trimmed)
		if len(matches) > 1 {
			drive := strings.ToUpper(matches[1])
			return fmt.Sprintf(`Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='%s:'" | Select-Object DeviceID, FreeSpace, Size | Format-List`, drive)
		}
	}

	return trimmed
}

func defaultCommandBlacklist() []string {
	return []string{"del ", "delete ", "erase ", "rd ", "rmdir ", "rm ", "remove-item ", "format ", "shutdown ", "reboot ", "restart-computer", "stop-service ", "sc stop ", "net stop ", "taskkill ", "kill ", "drop table ", "truncate table "}
}

func encodeStringSliceJSON(items []string) string {
	normalized := normalizeCommandRules(items)
	if normalized == nil {
		normalized = []string{}
	}
	raw, err := json.Marshal(normalized)
	if err != nil {
		return "[]"
	}
	return string(raw)
}

func decodeStringSliceJSON(raw string) []string {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return nil
	}

	var items []string
	if err := json.Unmarshal([]byte(trimmed), &items); err != nil {
		return nil
	}
	return normalizeCommandRules(items)
}

func cloneTask(task taskItem) taskItem {
	copied := task
	copied.Steps = append([]taskStep(nil), task.Steps...)
	return copied
}

func sanitizeUser(user userItem) userItem {
	user.PasswordHash = ""
	return user
}

func (s *appStore) getUserByTokenLocked(token string) (userItem, bool) {
	token = strings.TrimSpace(token)
	if token == "" {
		return userItem{}, false
	}

	session, ok := s.sessions[token]
	if !ok {
		return userItem{}, false
	}

	expiresAt, err := time.Parse(time.RFC3339, session.ExpiresAt)
	if err != nil || time.Now().UTC().After(expiresAt) {
		delete(s.sessions, token)
		s.persistAllLocked()
		return userItem{}, false
	}

	user, ok := s.users[session.UserID]
	if !ok || user.Status != "active" {
		return userItem{}, false
	}

	return user, true
}

func (s *appStore) getLatestTaskByConversationLocked(conversationID string) (taskItem, bool) {
	for i := len(s.taskOrder) - 1; i >= 0; i-- {
		taskID := s.taskOrder[i]
		task, ok := s.tasks[taskID]
		if ok && task.ConversationID == conversationID {
			return cloneTask(task), true
		}
	}

	return taskItem{}, false
}

func (s *appStore) appendConversationMessageLocked(conversationID, role, content string) {
	messageID := nextNumericID(&s.messageCounter)

	s.conversationMessages[conversationID] = append(s.conversationMessages[conversationID], conversationMessageItem{
		ID:             messageID,
		ConversationID: conversationID,
		Role:           role,
		Content:        strings.TrimSpace(content),
		CreatedAt:      time.Now().UTC().Format(time.RFC3339),
	})
}

func (s *appStore) appendConversationMessage(conversationID, role, content string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.appendConversationMessageLocked(conversationID, role, content)
	s.persistAllLocked()
}

func buildConversationTitle(messages []conversationMessageItem) string {
	for _, item := range messages {
		if item.Role == "user" && strings.TrimSpace(item.Content) != "" {
			return buildConversationExcerpt(item.Content)
		}
	}

	return "未命名会话"
}

func buildConversationExcerpt(content string) string {
	trimmed := strings.TrimSpace(content)
	if trimmed == "" {
		return ""
	}

	runes := []rune(trimmed)
	if len(runes) <= 32 {
		return trimmed
	}

	return string(runes[:32]) + "..."
}

func normalizeConversationMode(mode string) string {
	switch strings.ToLower(strings.TrimSpace(mode)) {
	case "chat":
		return "chat"
	default:
		return "task"
	}
}

func (s *appStore) buildChatReply(message string) string {
	model := strings.TrimSpace(s.settings.Model)
	if model == "" {
		model = "AITerm"
	}

	return fmt.Sprintf("模型 %s 已收到你的问题：%s\n\n当前为对话模式，你可以继续追问；如果需要自动执行，请切换到任务模式。", model, buildConversationExcerpt(message))
}

func hashPassword(password string) string {
	sum := sha256.Sum256([]byte(strings.TrimSpace(password)))
	return hex.EncodeToString(sum[:])
}

func generateSessionToken() string {
	buffer := make([]byte, 32)
	if _, err := rand.Read(buffer); err != nil {
		return fmt.Sprintf("fallback_%d", time.Now().UTC().UnixNano())
	}

	return hex.EncodeToString(buffer)
}

func normalizeUserRole(role, fallback string) string {
	switch strings.TrimSpace(role) {
	case "admin", "user":
		return strings.TrimSpace(role)
	case "":
		if fallback != "" {
			return fallback
		}
	}

	if fallback != "" {
		return fallback
	}

	return "user"
}

func normalizeUserStatus(status, fallback string) string {
	switch strings.TrimSpace(status) {
	case "active", "disabled":
		return strings.TrimSpace(status)
	case "":
		if fallback != "" {
			return fallback
		}
	}

	if fallback != "" {
		return fallback
	}

	return "active"
}

func (s *appStore) newUser(req userRequest) userItem {
	now := time.Now().UTC().Format(time.RFC3339)
	userID := nextNumericID(&s.userCounter)

	displayName := strings.TrimSpace(req.DisplayName)
	if displayName == "" {
		displayName = strings.TrimSpace(req.Username)
	}

	role := strings.TrimSpace(req.Role)
	if role == "" {
		role = "user"
	}

	status := strings.TrimSpace(req.Status)
	if status == "" {
		status = "active"
	}

	return userItem{
		ID:           userID,
		Username:     strings.ToLower(strings.TrimSpace(req.Username)),
		DisplayName:  displayName,
		Role:         role,
		Status:       status,
		CreatedAt:    now,
		UpdatedAt:    now,
		PasswordHash: hashPassword(req.Password),
	}
}

func (s *appStore) ensureBootstrapDataLocked() {
	if _, ok := s.nodes[defaultLocalNodeID]; !ok {
		s.nodes[defaultLocalNodeID] = nodeItem{
			ID:     defaultLocalNodeID,
			Name:   "local",
			Host:   "127.0.0.1",
			Port:   22,
			Status: "online",
		}
	}
	if !containsString(s.nodeOrder, defaultLocalNodeID) {
		s.nodeOrder = append([]string{defaultLocalNodeID}, removeString(s.nodeOrder, defaultLocalNodeID)...)
	}

	if s.activeAdminCountLocked() > 0 {
		return
	}

	username := "admin"
	if existing := s.findUserByUsernameLocked(username); existing != nil {
		username = fmt.Sprintf("admin_bootstrap_%d", s.userCounter)
	}

	admin := s.newUser(userRequest{
		Username:    username,
		DisplayName: "系统管理员",
		Password:    "12345678",
		Role:        "admin",
		Status:      "active",
	})
	s.users[admin.ID] = admin
	s.userOrder = append(s.userOrder, admin.ID)
}

func (s *appStore) activeAdminCountLocked() int {
	count := 0
	for _, userID := range s.userOrder {
		user, ok := s.users[userID]
		if ok && user.Role == "admin" && user.Status == "active" {
			count++
		}
	}

	return count
}

func (s *appStore) findUserByUsernameLocked(username string) *userItem {
	normalized := strings.ToLower(strings.TrimSpace(username))
	for _, userID := range s.userOrder {
		user, ok := s.users[userID]
		if ok && user.Username == normalized {
			cloned := user
			return &cloned
		}
	}

	return nil
}

func (s *appStore) deleteSessionsByUserLocked(userID string) {
	for token, session := range s.sessions {
		if session.UserID == userID {
			delete(s.sessions, token)
		}
	}
}

func sortConversationItems(items []conversationListItem) {
	for i := 0; i < len(items); i++ {
		for j := i + 1; j < len(items); j++ {
			if items[j].UpdatedAt > items[i].UpdatedAt || (items[j].UpdatedAt == items[i].UpdatedAt && items[j].ID > items[i].ID) {
				items[i], items[j] = items[j], items[i]
			}
		}
	}
}

func removeString(items []string, target string) []string {
	filtered := make([]string, 0, len(items))
	for _, item := range items {
		if item != target {
			filtered = append(filtered, item)
		}
	}

	return filtered
}

func containsString(items []string, target string) bool {
	for _, item := range items {
		if item == target {
			return true
		}
	}

	return false
}

func validatePassword(password string) error {
	if len(strings.TrimSpace(password)) < 8 {
		return fmt.Errorf("password must be at least 8 characters")
	}

	return nil
}

func (s *appStore) persistAllLocked() {
	switch {
	case s.mysql != nil:
		s.persistMySQLLocked()
	default:
		s.persistSQLiteLocked()
	}
}

func (s *appStore) recalculateCountersLocked() {
	s.taskCounter = maxTaskCounter(s.tasks, 1)
	s.nodeCounter = maxNodeCounter(s.nodes, 1)
	s.conversationCounter = maxConversationCounter(s.tasks, s.conversationMessages, 1)
	s.messageCounter = maxMessageCounter(s.conversationMessages, 1)
	s.userCounter = maxUserCounter(s.users, 1)
	s.sessionCounter = maxSessionCounter(s.sessions, 1)
}

func nextNumericID(counter *int) string {
	value := *counter
	*counter = *counter + 1
	return strconv.Itoa(value)
}
