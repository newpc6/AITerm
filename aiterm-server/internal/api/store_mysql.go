package api

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"

	_ "github.com/go-sql-driver/mysql"
)

type mysqlPersistence struct {
	db *sql.DB
}

func newMySQLPersistence(dsn string) (*mysqlPersistence, error) {
	if strings.TrimSpace(dsn) == "" {
		return nil, fmt.Errorf("mysql_dsn is required when database.driver=mysql")
	}

	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}

	if err := db.Ping(); err != nil {
		_ = db.Close()
		return nil, err
	}

	persistence := &mysqlPersistence{db: db}
	if err := persistence.initSchema(); err != nil {
		_ = db.Close()
		return nil, err
	}

	return persistence, nil
}

func (p *mysqlPersistence) initSchema() error {
	statements := []string{
		`CREATE TABLE IF NOT EXISTS settings (
			id BIGINT PRIMARY KEY AUTO_INCREMENT,
			api_url TEXT NOT NULL,
			api_key TEXT NOT NULL,
			model VARCHAR(255) NOT NULL,
			temperature DOUBLE NOT NULL,
			chat_system_prompt LONGTEXT NOT NULL,
			task_planner_prompt LONGTEXT NOT NULL,
			task_planner_user_prompt LONGTEXT NOT NULL,
			task_windows_tool_prompt LONGTEXT NOT NULL,
			task_linux_tool_prompt LONGTEXT NOT NULL,
			task_mac_tool_prompt LONGTEXT NOT NULL,
			task_failure_repair_prompt LONGTEXT NOT NULL,
			task_command_rules_prompt LONGTEXT NOT NULL,
			task_command_blacklist_json LONGTEXT NOT NULL,
			task_command_whitelist_json LONGTEXT NOT NULL,
			configured TINYINT(1) NOT NULL
		)`,
		`CREATE TABLE IF NOT EXISTS nodes (
			id BIGINT PRIMARY KEY AUTO_INCREMENT,
			name VARCHAR(255) NOT NULL,
			host VARCHAR(255) NOT NULL,
			port INT NOT NULL,
			status VARCHAR(255) NOT NULL
		)`,
		`CREATE TABLE IF NOT EXISTS tasks (
			id BIGINT PRIMARY KEY AUTO_INCREMENT,
			title VARCHAR(255) NOT NULL,
			status VARCHAR(64) NOT NULL,
			progress INT NOT NULL,
			conversation_id BIGINT NOT NULL,
			node_id BIGINT NOT NULL,
			request LONGTEXT NOT NULL,
			pending_command TEXT NOT NULL,
			risk_reason TEXT NOT NULL,
			summary TEXT NOT NULL,
			steps_json LONGTEXT NOT NULL,
			created_at VARCHAR(64) NOT NULL,
			updated_at VARCHAR(64) NOT NULL
		)`,
	}

	for _, statement := range statements {
		if _, err := p.db.Exec(statement); err != nil {
			return err
		}
	}

	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS api_key TEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS chat_system_prompt LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_planner_prompt LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_planner_user_prompt LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_windows_tool_prompt LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_linux_tool_prompt LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_mac_tool_prompt LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_failure_repair_prompt LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_command_rules_prompt LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_command_blacklist_json LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE settings ADD COLUMN IF NOT EXISTS task_command_whitelist_json LONGTEXT NOT NULL`)
	_, _ = p.db.Exec(`ALTER TABLE tasks ADD COLUMN IF NOT EXISTS request LONGTEXT NOT NULL`)

	return nil
}

func (s *appStore) loadFromMySQL() {
	if s.mysql == nil {
		return
	}

	var settings llmSettings
	var configured int
	var blacklistJSON string
	var whitelistJSON string
	err := s.mysql.db.QueryRow(`
SELECT api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, task_planner_user_prompt, task_windows_tool_prompt, task_linux_tool_prompt, task_mac_tool_prompt, task_failure_repair_prompt, task_command_rules_prompt, task_command_blacklist_json, task_command_whitelist_json, configured
FROM settings
WHERE id = 1
`).Scan(&settings.APIURL, &settings.APIKey, &settings.Model, &settings.Temperature, &settings.ChatSystemPrompt, &settings.TaskPlannerPrompt, &settings.TaskPlannerUserPrompt, &settings.TaskWindowsToolPrompt, &settings.TaskLinuxToolPrompt, &settings.TaskMacToolPrompt, &settings.TaskFailureRepairPrompt, &settings.TaskCommandRulesPrompt, &blacklistJSON, &whitelistJSON, &configured)
	if err == nil {
		settings.TaskCommandBlacklist = decodeStringSliceJSON(blacklistJSON)
		settings.TaskCommandWhitelist = decodeStringSliceJSON(whitelistJSON)
		settings.Configured = configured > 0 && settings.APIURL != "" && settings.Model != ""
		s.settings = settings
	}

	nodeRows, err := s.mysql.db.Query(`
SELECT CAST(id AS CHAR), name, host, port, status
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

	taskRows, err := s.mysql.db.Query(`
SELECT CAST(id AS CHAR), title, status, progress, CAST(conversation_id AS CHAR), CAST(node_id AS CHAR), request, pending_command, risk_reason, summary, steps_json, created_at, updated_at
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
}

func (s *appStore) persistMySQLLocked() {
	if s.mysql == nil {
		return
	}

	tx, err := s.mysql.db.Begin()
	if err != nil {
		return
	}
	defer tx.Rollback()

	if _, err = tx.Exec(`
INSERT INTO settings (id, api_url, api_key, model, temperature, chat_system_prompt, task_planner_prompt, task_planner_user_prompt, task_windows_tool_prompt, task_linux_tool_prompt, task_mac_tool_prompt, task_failure_repair_prompt, task_command_rules_prompt, task_command_blacklist_json, task_command_whitelist_json, configured)
VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON DUPLICATE KEY UPDATE
	api_url = VALUES(api_url),
	api_key = VALUES(api_key),
	model = VALUES(model),
	temperature = VALUES(temperature),
	chat_system_prompt = VALUES(chat_system_prompt),
	task_planner_prompt = VALUES(task_planner_prompt),
	task_planner_user_prompt = VALUES(task_planner_user_prompt),
	task_windows_tool_prompt = VALUES(task_windows_tool_prompt),
	task_linux_tool_prompt = VALUES(task_linux_tool_prompt),
	task_mac_tool_prompt = VALUES(task_mac_tool_prompt),
	task_failure_repair_prompt = VALUES(task_failure_repair_prompt),
	task_command_rules_prompt = VALUES(task_command_rules_prompt),
	task_command_blacklist_json = VALUES(task_command_blacklist_json),
	task_command_whitelist_json = VALUES(task_command_whitelist_json),
	configured = VALUES(configured)
`, s.settings.APIURL, s.settings.APIKey, s.settings.Model, s.settings.Temperature, s.settings.ChatSystemPrompt, s.settings.TaskPlannerPrompt, s.settings.TaskPlannerUserPrompt, s.settings.TaskWindowsToolPrompt, s.settings.TaskLinuxToolPrompt, s.settings.TaskMacToolPrompt, s.settings.TaskFailureRepairPrompt, s.settings.TaskCommandRulesPrompt, encodeStringSliceJSON(s.settings.TaskCommandBlacklist), encodeStringSliceJSON(s.settings.TaskCommandWhitelist), boolToInt(s.settings.Configured)); err != nil {
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

	_ = tx.Commit()
}
