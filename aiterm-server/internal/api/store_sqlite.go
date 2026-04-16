package api

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	_ "modernc.org/sqlite"
)

type sqlitePersistence struct {
	db *sql.DB
}

const sqliteSchema = `
CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  api_url TEXT NOT NULL,
  api_key TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL,
  temperature REAL NOT NULL,
  chat_system_prompt TEXT NOT NULL DEFAULT '',
  task_planner_prompt TEXT NOT NULL DEFAULT '',
  task_planner_user_prompt TEXT NOT NULL DEFAULT '',
  task_windows_tool_prompt TEXT NOT NULL DEFAULT '',
  task_linux_tool_prompt TEXT NOT NULL DEFAULT '',
  task_mac_tool_prompt TEXT NOT NULL DEFAULT '',
  task_failure_repair_prompt TEXT NOT NULL DEFAULT '',
  task_command_rules_prompt TEXT NOT NULL DEFAULT '',
  task_command_blacklist_json TEXT NOT NULL DEFAULT '[]',
  task_command_whitelist_json TEXT NOT NULL DEFAULT '[]',
  configured INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  enabled INTEGER NOT NULL,
  allow_password_login INTEGER NOT NULL,
  session_ttl_hours INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  host TEXT NOT NULL,
  port INTEGER NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  progress INTEGER NOT NULL,
  conversation_id INTEGER NOT NULL,
  node_id INTEGER NOT NULL,
  request TEXT NOT NULL DEFAULT '',
  pending_command TEXT NOT NULL,
  risk_reason TEXT NOT NULL,
  summary TEXT NOT NULL,
  steps_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL,
  status TEXT NOT NULL,
  last_login_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
`

func newSQLitePersistence(sqlitePath string) (*sqlitePersistence, error) {
	if err := os.MkdirAll(filepath.Dir(sqlitePath), 0o755); err != nil {
		return nil, err
	}

	db, err := sql.Open("sqlite", sqlitePath)
	if err != nil {
		return nil, err
	}

	persistence := &sqlitePersistence{db: db}
	if err := persistence.initSchema(); err != nil {
		_ = db.Close()
		return nil, err
	}

	return persistence, nil
}

func (p *sqlitePersistence) initSchema() error {
	if err := p.migrateLegacyTextIDs(); err != nil {
		return err
	}

	_, err := p.db.Exec(sqliteSchema)
	if err != nil {
		return err
	}
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN api_key TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN chat_system_prompt TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_planner_prompt TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_planner_user_prompt TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_windows_tool_prompt TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_linux_tool_prompt TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_mac_tool_prompt TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_failure_repair_prompt TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_command_rules_prompt TEXT NOT NULL DEFAULT ''`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_command_blacklist_json TEXT NOT NULL DEFAULT '[]'`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN task_command_whitelist_json TEXT NOT NULL DEFAULT '[]'`)
	_, _ = p.db.Exec(`ALTER TABLE tasks ADD COLUMN request TEXT NOT NULL DEFAULT ''`)
	return nil
}

func (p *sqlitePersistence) migrateLegacyTextIDs() error {
	legacy, err := p.hasLegacyTextIDSchema()
	if err != nil || !legacy {
		return err
	}

	settings, hasSettings, err := p.loadLegacySettings()
	if err != nil {
		return err
	}
	auth, hasAuth, err := p.loadLegacyAuthSettings()
	if err != nil {
		return err
	}
	nodes, err := p.loadLegacyNodes()
	if err != nil {
		return err
	}
	tasks, err := p.loadLegacyTasks()
	if err != nil {
		return err
	}
	messages, err := p.loadLegacyMessages()
	if err != nil {
		return err
	}
	users, err := p.loadLegacyUsers()
	if err != nil {
		return err
	}
	sessions, err := p.loadLegacySessions()
	if err != nil {
		return err
	}

	nodeIDs := buildLegacyIDMapFromNodes(nodes)
	conversationIDs := buildLegacyConversationIDMap(messages, tasks)
	taskIDs := buildLegacyIDMapFromTasks(tasks)
	messageIDs := buildLegacyIDMapFromMessages(messages)
	userIDs := buildLegacyIDMapFromUsers(users)
	sessionIDs := buildLegacyIDMapFromSessions(sessions)

	tx, err := p.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	dropStatements := []string{
		`DROP TABLE IF EXISTS settings`,
		`DROP TABLE IF EXISTS auth_settings`,
		`DROP TABLE IF EXISTS nodes`,
		`DROP TABLE IF EXISTS tasks`,
		`DROP TABLE IF EXISTS conversation_messages`,
		`DROP TABLE IF EXISTS users`,
		`DROP TABLE IF EXISTS sessions`,
	}
	for _, statement := range dropStatements {
		if _, err := tx.Exec(statement); err != nil {
			return err
		}
	}

	if _, err := tx.Exec(sqliteSchema); err != nil {
		return err
	}

	if hasSettings {
		if _, err := tx.Exec(`
INSERT INTO settings (id, api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, task_planner_user_prompt, task_windows_tool_prompt, task_linux_tool_prompt, task_mac_tool_prompt, task_command_rules_prompt, task_command_blacklist_json, task_command_whitelist_json, configured)
VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
`, settings.APIURL, settings.APIKey, settings.Model, settings.Temperature, settings.ChatSystemPrompt, settings.TaskPlannerPrompt, settings.TaskPlannerUserPrompt, settings.TaskWindowsToolPrompt, settings.TaskLinuxToolPrompt, settings.TaskMacToolPrompt, settings.TaskCommandRulesPrompt, encodeStringSliceJSON(settings.TaskCommandBlacklist), encodeStringSliceJSON(settings.TaskCommandWhitelist), boolToInt(settings.Configured)); err != nil {
			return err
		}
	}

	if hasAuth {
		if _, err := tx.Exec(`
INSERT INTO auth_settings (id, enabled, allow_password_login, session_ttl_hours)
VALUES (1, ?, ?, ?)
`, boolToInt(auth.Enabled), boolToInt(auth.AllowPasswordLogin), auth.SessionTTLHours); err != nil {
			return err
		}
	}

	for _, node := range nodes {
		if _, err := tx.Exec(`
INSERT INTO nodes (id, name, host, port, status)
VALUES (?, ?, ?, ?, ?)
`, nodeIDs[node.ID], node.Name, node.Host, node.Port, node.Status); err != nil {
			return err
		}
	}

	for _, task := range tasks {
		stepsJSON, marshalErr := json.Marshal(task.Steps)
		if marshalErr != nil {
			return marshalErr
		}
		if _, err := tx.Exec(`
INSERT INTO tasks (id, title, status, progress, conversation_id, node_id, request, pending_command, risk_reason, summary, steps_json, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
`, taskIDs[task.ID], task.Title, task.Status, task.Progress, conversationIDs[task.ConversationID], nodeIDs[task.NodeID], task.Request, task.PendingCommand, task.RiskReason, task.Summary, string(stepsJSON), task.CreatedAt, task.UpdatedAt); err != nil {
			return err
		}
	}

	for _, item := range messages {
		if _, err := tx.Exec(`
INSERT INTO conversation_messages (id, conversation_id, role, content, created_at)
VALUES (?, ?, ?, ?, ?)
`, messageIDs[item.ID], conversationIDs[item.ConversationID], item.Role, item.Content, item.CreatedAt); err != nil {
			return err
		}
	}

	for _, user := range users {
		if _, err := tx.Exec(`
INSERT INTO users (id, username, display_name, password_hash, role, status, last_login_at, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
`, userIDs[user.ID], user.Username, user.DisplayName, user.PasswordHash, user.Role, user.Status, user.LastLoginAt, user.CreatedAt, user.UpdatedAt); err != nil {
			return err
		}
	}

	for _, session := range sessions {
		if _, err := tx.Exec(`
INSERT INTO sessions (id, token, user_id, created_at, expires_at)
VALUES (?, ?, ?, ?, ?)
`, sessionIDs[session.ID], session.Token, userIDs[session.UserID], session.CreatedAt, session.ExpiresAt); err != nil {
			return err
		}
	}

	return tx.Commit()
}

func (p *sqlitePersistence) hasLegacyTextIDSchema() (bool, error) {
	columnType, exists, err := p.lookupColumnType("nodes", "id")
	if err != nil || !exists {
		return false, err
	}
	return strings.Contains(strings.ToUpper(columnType), "TEXT"), nil
}

func (p *sqlitePersistence) lookupColumnType(tableName, columnName string) (string, bool, error) {
	rows, err := p.db.Query(fmt.Sprintf(`PRAGMA table_info(%s)`, tableName))
	if err != nil {
		return "", false, err
	}
	defer rows.Close()

	for rows.Next() {
		var cid int
		var name string
		var columnType string
		var notNull int
		var defaultValue interface{}
		var pk int
		if scanErr := rows.Scan(&cid, &name, &columnType, &notNull, &defaultValue, &pk); scanErr != nil {
			return "", false, scanErr
		}
		if name == columnName {
			return columnType, true, nil
		}
	}

	return "", false, nil
}

func (p *sqlitePersistence) loadLegacySettings() (llmSettings, bool, error) {
	var settings llmSettings
	var configured int
	var blacklistJSON string
	var whitelistJSON string
	err := p.db.QueryRow(`
SELECT api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, task_planner_user_prompt, task_windows_tool_prompt, task_linux_tool_prompt, task_mac_tool_prompt, task_failure_repair_prompt, task_command_rules_prompt, task_command_blacklist_json, task_command_whitelist_json, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &settings.ChatSystemPrompt, &settings.TaskPlannerPrompt, &settings.TaskPlannerUserPrompt, &settings.TaskWindowsToolPrompt, &settings.TaskLinuxToolPrompt, &settings.TaskMacToolPrompt, &settings.TaskFailureRepairPrompt, &settings.TaskCommandRulesPrompt, &blacklistJSON, &whitelistJSON, &configured)
	if err == sql.ErrNoRows {
		return llmSettings{}, false, nil
	}
	if err != nil {
		err = p.db.QueryRow(`
SELECT api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &settings.ChatSystemPrompt, &settings.TaskPlannerPrompt, &configured)
	}
	if err != nil {
		err = p.db.QueryRow(`
SELECT api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &settings.ChatSystemPrompt, &settings.TaskPlannerPrompt, &configured)
	}
	if err != nil {
		err = p.db.QueryRow(`
SELECT api_url, api_key, model, temperature, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &configured)
	}
	if err != nil {
		err = p.db.QueryRow(`
SELECT api_url, model, temperature, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.Model, &settings.Temperature, &configured)
	}
	if err == sql.ErrNoRows {
		return llmSettings{}, false, nil
	}
	if err != nil {
		return llmSettings{}, false, err
	}
	settings.TaskCommandBlacklist = decodeStringSliceJSON(blacklistJSON)
	settings.TaskCommandWhitelist = decodeStringSliceJSON(whitelistJSON)
	settings.Configured = configured > 0 && settings.APIURL != "" && settings.Model != ""
	return settings, true, nil
}

func (p *sqlitePersistence) loadLegacyAuthSettings() (authSettings, bool, error) {
	var auth authSettings
	var enabled int
	var allowPasswordLogin int
	err := p.db.QueryRow(`
SELECT enabled, allow_password_login, session_ttl_hours
FROM auth_settings
WHERE id = 1
`).Scan(&enabled, &allowPasswordLogin, &auth.SessionTTLHours)
	if err == sql.ErrNoRows {
		return authSettings{}, false, nil
	}
	if err != nil {
		return authSettings{}, false, err
	}
	auth.Enabled = enabled > 0
	auth.AllowPasswordLogin = allowPasswordLogin > 0
	return auth, true, nil
}

func (p *sqlitePersistence) loadLegacyNodes() ([]nodeItem, error) {
	rows, err := p.db.Query(`
SELECT id, name, host, port, status
FROM nodes
ORDER BY id ASC
`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := make([]nodeItem, 0)
	for rows.Next() {
		var item nodeItem
		if scanErr := rows.Scan(&item.ID, &item.Name, &item.Host, &item.Port, &item.Status); scanErr != nil {
			return nil, scanErr
		}
		items = append(items, item)
	}
	return items, nil
}

func (p *sqlitePersistence) loadLegacyTasks() ([]taskItem, error) {
	rows, err := p.db.Query(`
SELECT id, title, status, progress, conversation_id, node_id, request, pending_command, risk_reason, summary, steps_json, created_at, updated_at
FROM tasks
ORDER BY created_at ASC, id ASC
`)
	if err != nil {
		rows, err = p.db.Query(`
SELECT id, title, status, progress, conversation_id, node_id, pending_command, risk_reason, summary, steps_json, created_at, updated_at
FROM tasks
ORDER BY created_at ASC, id ASC
`)
		if err != nil {
			return nil, err
		}
		defer rows.Close()

		items := make([]taskItem, 0)
		for rows.Next() {
			var item taskItem
			var stepsJSON string
			if scanErr := rows.Scan(
				&item.ID,
				&item.Title,
				&item.Status,
				&item.Progress,
				&item.ConversationID,
				&item.NodeID,
				&item.PendingCommand,
				&item.RiskReason,
				&item.Summary,
				&stepsJSON,
				&item.CreatedAt,
				&item.UpdatedAt,
			); scanErr != nil {
				return nil, scanErr
			}
			if unmarshalErr := json.Unmarshal([]byte(stepsJSON), &item.Steps); unmarshalErr != nil {
				item.Steps = nil
			}
			items = append(items, item)
		}
		return items, nil
	}
	defer rows.Close()

	items := make([]taskItem, 0)
	for rows.Next() {
		var item taskItem
		var stepsJSON string
		if scanErr := rows.Scan(
			&item.ID,
			&item.Title,
			&item.Status,
			&item.Progress,
			&item.ConversationID,
			&item.NodeID,
			&item.Request,
			&item.PendingCommand,
			&item.RiskReason,
			&item.Summary,
			&stepsJSON,
			&item.CreatedAt,
			&item.UpdatedAt,
		); scanErr != nil {
			return nil, scanErr
		}
		if unmarshalErr := json.Unmarshal([]byte(stepsJSON), &item.Steps); unmarshalErr != nil {
			item.Steps = nil
		}
		items = append(items, item)
	}
	return items, nil
}

func (p *sqlitePersistence) loadLegacyMessages() ([]conversationMessageItem, error) {
	rows, err := p.db.Query(`
SELECT id, conversation_id, role, content, created_at
FROM conversation_messages
ORDER BY created_at ASC, id ASC
`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := make([]conversationMessageItem, 0)
	for rows.Next() {
		var item conversationMessageItem
		if scanErr := rows.Scan(&item.ID, &item.ConversationID, &item.Role, &item.Content, &item.CreatedAt); scanErr != nil {
			return nil, scanErr
		}
		items = append(items, item)
	}
	return items, nil
}

func (p *sqlitePersistence) loadLegacyUsers() ([]userItem, error) {
	rows, err := p.db.Query(`
SELECT id, username, display_name, password_hash, role, status, last_login_at, created_at, updated_at
FROM users
ORDER BY id ASC
`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := make([]userItem, 0)
	for rows.Next() {
		var item userItem
		if scanErr := rows.Scan(&item.ID, &item.Username, &item.DisplayName, &item.PasswordHash, &item.Role, &item.Status, &item.LastLoginAt, &item.CreatedAt, &item.UpdatedAt); scanErr != nil {
			return nil, scanErr
		}
		items = append(items, item)
	}
	return items, nil
}

func (p *sqlitePersistence) loadLegacySessions() ([]sessionItem, error) {
	rows, err := p.db.Query(`
SELECT id, token, user_id, created_at, expires_at
FROM sessions
ORDER BY id ASC
`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := make([]sessionItem, 0)
	for rows.Next() {
		var item sessionItem
		if scanErr := rows.Scan(&item.ID, &item.Token, &item.UserID, &item.CreatedAt, &item.ExpiresAt); scanErr != nil {
			return nil, scanErr
		}
		items = append(items, item)
	}
	return items, nil
}

func buildLegacyIDMapFromNodes(items []nodeItem) map[string]string {
	ids := make(map[string]string, len(items))
	for index, item := range items {
		ids[item.ID] = strconv.Itoa(index + 1)
	}
	return ids
}

func buildLegacyIDMapFromTasks(items []taskItem) map[string]string {
	ids := make(map[string]string, len(items))
	for index, item := range items {
		ids[item.ID] = strconv.Itoa(index + 1)
	}
	return ids
}

func buildLegacyIDMapFromMessages(items []conversationMessageItem) map[string]string {
	ids := make(map[string]string, len(items))
	for index, item := range items {
		ids[item.ID] = strconv.Itoa(index + 1)
	}
	return ids
}

func buildLegacyIDMapFromUsers(items []userItem) map[string]string {
	ids := make(map[string]string, len(items))
	for index, item := range items {
		ids[item.ID] = strconv.Itoa(index + 1)
	}
	return ids
}

func buildLegacyIDMapFromSessions(items []sessionItem) map[string]string {
	ids := make(map[string]string, len(items))
	for index, item := range items {
		ids[item.ID] = strconv.Itoa(index + 1)
	}
	return ids
}

func buildLegacyConversationIDMap(messages []conversationMessageItem, tasks []taskItem) map[string]string {
	ids := make(map[string]string)
	nextID := 1
	for _, item := range messages {
		if _, exists := ids[item.ConversationID]; !exists {
			ids[item.ConversationID] = strconv.Itoa(nextID)
			nextID++
		}
	}
	for _, item := range tasks {
		if _, exists := ids[item.ConversationID]; !exists {
			ids[item.ConversationID] = strconv.Itoa(nextID)
			nextID++
		}
	}
	return ids
}

func (s *appStore) loadFromSQLite() {
	if s.sqlite == nil {
		return
	}

	var settings llmSettings
	var configured int
	var blacklistJSON string
	var whitelistJSON string
	err := s.sqlite.db.QueryRow(`
SELECT api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, task_planner_user_prompt, task_windows_tool_prompt, task_linux_tool_prompt, task_mac_tool_prompt, task_failure_repair_prompt, task_command_rules_prompt, task_command_blacklist_json, task_command_whitelist_json, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &settings.ChatSystemPrompt, &settings.TaskPlannerPrompt, &settings.TaskPlannerUserPrompt, &settings.TaskWindowsToolPrompt, &settings.TaskLinuxToolPrompt, &settings.TaskMacToolPrompt, &settings.TaskFailureRepairPrompt, &settings.TaskCommandRulesPrompt, &blacklistJSON, &whitelistJSON, &configured)
	if err != nil {
		err = s.sqlite.db.QueryRow(`
SELECT api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &settings.ChatSystemPrompt, &settings.TaskPlannerPrompt, &configured)
	}
	if err != nil {
		err = s.sqlite.db.QueryRow(`
SELECT api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &settings.ChatSystemPrompt, &settings.TaskPlannerPrompt, &configured)
	}
	if err != nil {
		err = s.sqlite.db.QueryRow(`
SELECT api_url, api_key, model, temperature, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &configured)
	}
	if err != nil {
		err = s.sqlite.db.QueryRow(`
SELECT api_url, model, temperature, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.Model, &settings.Temperature, &configured)
	}
	if err == nil {
		settings.TaskCommandBlacklist = decodeStringSliceJSON(blacklistJSON)
		settings.TaskCommandWhitelist = decodeStringSliceJSON(whitelistJSON)
		settings.Configured = configured > 0 && settings.APIURL != "" && settings.Model != ""
		s.settings = settings
	}

	var auth authSettings
	var enabled int
	var allowPasswordLogin int
	err = s.sqlite.db.QueryRow(`
SELECT enabled, allow_password_login, session_ttl_hours
FROM auth_settings
WHERE id = 1
`).Scan(&enabled, &allowPasswordLogin, &auth.SessionTTLHours)
	if err == nil {
		auth.Enabled = enabled > 0
		auth.AllowPasswordLogin = allowPasswordLogin > 0
		s.authSettings = auth
	}

	nodeRows, err := s.sqlite.db.Query(`
SELECT CAST(id AS TEXT), name, host, port, status
FROM nodes
ORDER BY id ASC
`)
	if err == nil {
		defer nodeRows.Close()

		nodes := make(map[string]nodeItem)
		order := make([]string, 0)
		for nodeRows.Next() {
			var node nodeItem
			if scanErr := nodeRows.Scan(&node.ID, &node.Name, &node.Host, &node.Port, &node.Status); scanErr != nil {
				continue
			}

			nodes[node.ID] = node
			order = append(order, node.ID)
		}

		if len(nodes) > 0 {
			s.nodes = nodes
			s.nodeOrder = order
		}
	}

	taskRows, err := s.sqlite.db.Query(`
SELECT CAST(id AS TEXT), title, status, progress, CAST(conversation_id AS TEXT), CAST(node_id AS TEXT), request, pending_command, risk_reason, summary, steps_json, created_at, updated_at
FROM tasks
ORDER BY created_at ASC, id ASC
`)
	if err == nil {
		defer taskRows.Close()

		tasks := make(map[string]taskItem)
		order := make([]string, 0)
		for taskRows.Next() {
			var task taskItem
			var stepsJSON string
			if scanErr := taskRows.Scan(
				&task.ID,
				&task.Title,
				&task.Status,
				&task.Progress,
				&task.ConversationID,
				&task.NodeID,
				&task.Request,
				&task.PendingCommand,
				&task.RiskReason,
				&task.Summary,
				&stepsJSON,
				&task.CreatedAt,
				&task.UpdatedAt,
			); scanErr != nil {
				continue
			}

			if unmarshalErr := json.Unmarshal([]byte(stepsJSON), &task.Steps); unmarshalErr != nil {
				task.Steps = nil
			}

			tasks[task.ID] = task
			order = append(order, task.ID)
		}

		if len(tasks) > 0 {
			s.tasks = tasks
			s.taskOrder = order
		}
	}

	messageRows, err := s.sqlite.db.Query(`
SELECT CAST(id AS TEXT), CAST(conversation_id AS TEXT), role, content, created_at
FROM conversation_messages
ORDER BY created_at ASC, id ASC
`)
	if err == nil {
		defer messageRows.Close()

		conversationMessages := make(map[string][]conversationMessageItem)
		for messageRows.Next() {
			var item conversationMessageItem
			if scanErr := messageRows.Scan(
				&item.ID,
				&item.ConversationID,
				&item.Role,
				&item.Content,
				&item.CreatedAt,
			); scanErr != nil {
				continue
			}

			conversationMessages[item.ConversationID] = append(conversationMessages[item.ConversationID], item)
		}

		if len(conversationMessages) > 0 {
			s.conversationMessages = conversationMessages
		}
	}

	userRows, err := s.sqlite.db.Query(`
SELECT CAST(id AS TEXT), username, display_name, password_hash, role, status, last_login_at, created_at, updated_at
FROM users
ORDER BY id ASC
`)
	if err == nil {
		defer userRows.Close()

		users := make(map[string]userItem)
		order := make([]string, 0)
		for userRows.Next() {
			var user userItem
			if scanErr := userRows.Scan(
				&user.ID,
				&user.Username,
				&user.DisplayName,
				&user.PasswordHash,
				&user.Role,
				&user.Status,
				&user.LastLoginAt,
				&user.CreatedAt,
				&user.UpdatedAt,
			); scanErr != nil {
				continue
			}

			users[user.ID] = user
			order = append(order, user.ID)
		}

		if len(users) > 0 {
			s.users = users
			s.userOrder = order
		}
	}

	sessionRows, err := s.sqlite.db.Query(`
SELECT CAST(id AS TEXT), token, CAST(user_id AS TEXT), created_at, expires_at
FROM sessions
ORDER BY id ASC
`)
	if err == nil {
		defer sessionRows.Close()

		sessions := make(map[string]sessionItem)
		for sessionRows.Next() {
			var session sessionItem
			if scanErr := sessionRows.Scan(
				&session.ID,
				&session.Token,
				&session.UserID,
				&session.CreatedAt,
				&session.ExpiresAt,
			); scanErr != nil {
				continue
			}

			sessions[session.Token] = session
		}

		if len(sessions) > 0 {
			s.sessions = sessions
		}
	}
}

func (s *appStore) persistSQLiteLocked() {
	if s.sqlite == nil {
		return
	}

	tx, err := s.sqlite.db.Begin()
	if err != nil {
		return
	}
	defer tx.Rollback()

	if _, err = tx.Exec(`
INSERT INTO settings (id, api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, task_planner_user_prompt, task_windows_tool_prompt, task_linux_tool_prompt, task_mac_tool_prompt, task_failure_repair_prompt, task_command_rules_prompt, task_command_blacklist_json, task_command_whitelist_json, configured)
VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
  api_url = excluded.api_url,
  api_key = excluded.api_key,
  model = excluded.model,
  temperature = excluded.temperature,
  chat_system_prompt = excluded.chat_system_prompt,
  task_planner_prompt = excluded.task_planner_prompt,
  task_planner_user_prompt = excluded.task_planner_user_prompt,
  task_windows_tool_prompt = excluded.task_windows_tool_prompt,
  task_linux_tool_prompt = excluded.task_linux_tool_prompt,
  task_mac_tool_prompt = excluded.task_mac_tool_prompt,
  task_failure_repair_prompt = excluded.task_failure_repair_prompt,
  task_command_rules_prompt = excluded.task_command_rules_prompt,
  task_command_blacklist_json = excluded.task_command_blacklist_json,
  task_command_whitelist_json = excluded.task_command_whitelist_json,
  configured = excluded.configured
`, s.settings.APIURL, s.settings.APIKey, s.settings.Model, s.settings.Temperature, s.settings.ChatSystemPrompt, s.settings.TaskPlannerPrompt, s.settings.TaskPlannerUserPrompt, s.settings.TaskWindowsToolPrompt, s.settings.TaskLinuxToolPrompt, s.settings.TaskMacToolPrompt, s.settings.TaskFailureRepairPrompt, s.settings.TaskCommandRulesPrompt, encodeStringSliceJSON(s.settings.TaskCommandBlacklist), encodeStringSliceJSON(s.settings.TaskCommandWhitelist), boolToInt(s.settings.Configured)); err != nil {
		return
	}

	if _, err = tx.Exec(`
INSERT INTO auth_settings (id, enabled, allow_password_login, session_ttl_hours)
VALUES (1, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
  enabled = excluded.enabled,
  allow_password_login = excluded.allow_password_login,
  session_ttl_hours = excluded.session_ttl_hours
`, boolToInt(s.authSettings.Enabled), boolToInt(s.authSettings.AllowPasswordLogin), s.authSettings.SessionTTLHours); err != nil {
		return
	}

	if _, err = tx.Exec(`DELETE FROM nodes`); err != nil {
		return
	}

	for _, nodeID := range s.nodeOrder {
		node, ok := s.nodes[nodeID]
		if !ok {
			continue
		}

		if _, err = tx.Exec(`
INSERT INTO nodes (id, name, host, port, status)
VALUES (?, ?, ?, ?, ?)
`, node.ID, node.Name, node.Host, node.Port, node.Status); err != nil {
			return
		}
	}

	if _, err = tx.Exec(`DELETE FROM tasks`); err != nil {
		return
	}

	for _, taskID := range s.taskOrder {
		task, ok := s.tasks[taskID]
		if !ok {
			continue
		}

		stepsJSON, marshalErr := json.Marshal(task.Steps)
		if marshalErr != nil {
			return
		}

		if _, err = tx.Exec(`
INSERT INTO tasks (id, title, status, progress, conversation_id, node_id, request, pending_command, risk_reason, summary, steps_json, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
`, task.ID, task.Title, task.Status, task.Progress, task.ConversationID, task.NodeID, task.Request, task.PendingCommand, task.RiskReason, task.Summary, string(stepsJSON), task.CreatedAt, task.UpdatedAt); err != nil {
			return
		}
	}

	if _, err = tx.Exec(`DELETE FROM conversation_messages`); err != nil {
		return
	}

	for _, items := range s.conversationMessages {
		for _, item := range items {
			if _, err = tx.Exec(`
INSERT INTO conversation_messages (id, conversation_id, role, content, created_at)
VALUES (?, ?, ?, ?, ?)
`, item.ID, item.ConversationID, item.Role, item.Content, item.CreatedAt); err != nil {
				return
			}
		}
	}

	if _, err = tx.Exec(`DELETE FROM users`); err != nil {
		return
	}

	for _, userID := range s.userOrder {
		user, ok := s.users[userID]
		if !ok {
			continue
		}

		if _, err = tx.Exec(`
INSERT INTO users (id, username, display_name, password_hash, role, status, last_login_at, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
`, user.ID, user.Username, user.DisplayName, user.PasswordHash, user.Role, user.Status, user.LastLoginAt, user.CreatedAt, user.UpdatedAt); err != nil {
			return
		}
	}

	if _, err = tx.Exec(`DELETE FROM sessions`); err != nil {
		return
	}

	for _, session := range s.sessions {
		if _, err = tx.Exec(`
INSERT INTO sessions (id, token, user_id, created_at, expires_at)
VALUES (?, ?, ?, ?, ?)
`, session.ID, session.Token, session.UserID, session.CreatedAt, session.ExpiresAt); err != nil {
			return
		}
	}

	_ = tx.Commit()
}

func maxTaskCounter(tasks map[string]taskItem, fallback int) int {
	maxCounter := fallback
	for taskID := range tasks {
		index, ok := parseNumericCounter(taskID)
		if ok && index >= maxCounter {
			maxCounter = index + 1
		}
	}

	return maxCounter
}

func maxNodeCounter(nodes map[string]nodeItem, fallback int) int {
	maxCounter := fallback
	for nodeID := range nodes {
		index, ok := parseNumericCounter(nodeID)
		if ok && index >= maxCounter {
			maxCounter = index + 1
		}
	}

	return maxCounter
}

func maxConversationCounter(tasks map[string]taskItem, conversationMessages map[string][]conversationMessageItem, fallback int) int {
	maxCounter := fallback
	for _, task := range tasks {
		index, ok := parseNumericCounter(task.ConversationID)
		if ok && index >= maxCounter {
			maxCounter = index + 1
		}
	}
	for conversationID := range conversationMessages {
		index, ok := parseNumericCounter(conversationID)
		if ok && index >= maxCounter {
			maxCounter = index + 1
		}
	}

	return maxCounter
}

func boolToInt(value bool) int {
	if value {
		return 1
	}

	return 0
}

func maxMessageCounter(conversationMessages map[string][]conversationMessageItem, fallback int) int {
	maxCounter := fallback
	for _, items := range conversationMessages {
		for _, item := range items {
			index, ok := parseNumericCounter(item.ID)
			if ok && index >= maxCounter {
				maxCounter = index + 1
			}
		}
	}

	return maxCounter
}

func maxUserCounter(users map[string]userItem, fallback int) int {
	maxCounter := fallback
	for userID := range users {
		index, ok := parseNumericCounter(userID)
		if ok && index >= maxCounter {
			maxCounter = index + 1
		}
	}

	return maxCounter
}

func maxSessionCounter(sessions map[string]sessionItem, fallback int) int {
	maxCounter := fallback
	for _, session := range sessions {
		index, ok := parseNumericCounter(session.ID)
		if ok && index >= maxCounter {
			maxCounter = index + 1
		}
	}

	return maxCounter
}

func parseNumericCounter(value string) (int, bool) {
	parsed, err := strconv.Atoi(strings.TrimSpace(value))
	if err != nil || parsed <= 0 {
		return 0, false
	}
	return parsed, true
}
