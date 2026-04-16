package config

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
)

type DatabaseConfig struct {
	Driver     string `json:"driver"`
	SQLitePath string `json:"sqlite_path"`
	MySQLDSN   string `json:"mysql_dsn"`
}

type CORSConfig struct {
	AllowedOrigins []string `json:"allowed_origins"`
}

type LogConfig struct {
	Enabled      bool `json:"enabled"`
	RequestBody  int  `json:"request_body"`
	ResponseBody int  `json:"response_body"`
}

type LLMConfig struct {
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
}

type Config struct {
	Port     int            `json:"port"`
	DataDir  string         `json:"data_dir"`
	Database DatabaseConfig `json:"database"`
	CORS     CORSConfig     `json:"cors"`
	Log      LogConfig      `json:"log"`
	LLM      LLMConfig      `json:"llm"`
}

func Load() Config {
	cfg := defaultConfig()
	configPath := filepath.Join("configs", "app.json")

	if raw, err := os.ReadFile(configPath); err == nil {
		raw = bytes.TrimPrefix(raw, []byte{0xEF, 0xBB, 0xBF})
		_ = json.Unmarshal(raw, &cfg)
	}

	normalize(&cfg)

	return cfg
}

func defaultConfig() Config {
	return Config{
		Port:    8080,
		DataDir: "data",
		Database: DatabaseConfig{
			Driver:     "sqlite",
			SQLitePath: filepath.Join("data", "aiterm.db"),
			MySQLDSN:   "",
		},
		CORS: CORSConfig{
			AllowedOrigins: []string{
				"http://localhost:5173",
				"http://127.0.0.1:5173",
			},
		},
		Log: LogConfig{
			Enabled:      true,
			RequestBody:  128,
			ResponseBody: 128,
		},
		LLM: LLMConfig{
			ChatSystemPrompt:        "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。当前选中节点：{{node_description}}。只有当用户问题涉及执行、部署、排障、环境差异时，再结合该节点上下文给出建议。",
			TaskPlannerPrompt:       "你是 AITerm 的任务规划器。你的职责是把用户请求转换为可以在当前节点逐步执行的任务计划。当前节点：{{node_description}}。用户请求：{{user_request}}。请优先生成最小可执行步骤；复杂任务可以拆分为多个步骤；如果任务可能破坏数据、删除文件、停止服务、修改系统状态或存在明显风险，请标记需要人工确认。",
			TaskPlannerUserPrompt:   "请基于以下用户请求生成任务计划，并为每一步提供可直接执行的命令。\n用户请求：{{user_request}}{{conversation_history}}\n\n要求：\n1. 根据情况拆分返回合适数量的可执行步骤。\n2. 每个步骤都要有简短 title 和 command。\n3. command 必须可直接在目标节点 shell 中执行，不要生成仅用于打开交互式终端的命令，例如 cmd.exe、powershell.exe、bash、sh。\n4. 优先在命令和结果中直接转换为更适合人查看的单位和格式。",
			TaskWindowsToolPrompt:   "当前系统为 Windows。命令优先使用 PowerShell 或系统自带命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 Invoke-WebRequest 或 curl.exe，并显式写出完整保存路径；删除文件或目录优先用 Remove-Item，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 Move-Item；复制文件优先用 Copy-Item；查看文件内容优先用 Get-Content；列出目录优先用 Get-ChildItem；查找文件优先用 Get-ChildItem -Recurse 或 dir；查询文本可用 Select-String；创建目录可用 New-Item -ItemType Directory；压缩或解压可用 Compress-Archive、Expand-Archive。",
			TaskLinuxToolPrompt:     "当前系统为 Linux。命令优先使用通用 shell 命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 curl -L 或 wget，并显式写出完整保存路径；删除文件或目录优先用 rm，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 mv；复制文件优先用 cp；查看文件内容优先用 cat、sed、tail、head；列出目录优先用 ls；查找文件优先用 find；查询文本优先用 grep；创建目录优先用 mkdir -p；压缩或解压优先用 tar、unzip、gzip。",
			TaskMacToolPrompt:       "当前系统为 macOS。命令优先使用 zsh/bash 兼容命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 curl -L，并显式写出完整保存路径；删除文件或目录优先用 rm，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 mv；复制文件优先用 cp；查看文件内容优先用 cat、sed、tail、head；列出目录优先用 ls；查找文件优先用 find 或 mdfind；查询文本优先用 grep；创建目录优先用 mkdir -p；压缩或解压优先用 tar、unzip。",
			TaskFailureRepairPrompt: "请分析以下自动化任务失败信息，并返回修正结果。任务请求：{{user_request}}\n节点：{{node_description}}\n失败步骤：{{step_title}}\n失败命令：{{failed_command}}\n执行输出：{{execution_output}}\n失败提示：{{failure_text}}\n\n要求：\n1. 先判断失败最可能的原因。\n2. 如果可以修正，请返回一个可直接执行的 corrected_command；如果不适合继续自动执行，则 corrected_command 置空。\n3. corrected_command 必须是单条、可直接执行的命令，不要返回解释性文本。\n4. 如需修正标题，可填写 corrected_title，否则留空。\n5. 只返回 JSON，不要输出 markdown，不要输出解释。JSON 结构固定为：{\"reason\":\"\",\"suggestion\":\"\",\"corrected_title\":\"\",\"corrected_command\":\"\"}",
			TaskCommandRulesPrompt:  "\n\n命令风控规则：{{command_rules}}",
			TaskCommandBlacklist:    []string{"del ", "delete ", "erase ", "rd ", "rmdir ", "rm ", "remove-item ", "format ", "shutdown ", "reboot ", "restart-computer", "stop-service ", "sc stop ", "net stop ", "taskkill ", "kill ", "drop table ", "truncate table "},
			TaskCommandWhitelist:    []string{},
		},
	}
}

func normalize(cfg *Config) {
	if cfg.Port <= 0 {
		cfg.Port = 8080
	}

	if cfg.DataDir == "" {
		cfg.DataDir = "data"
	}

	if cfg.Database.Driver == "" {
		cfg.Database.Driver = "sqlite"
	}

	if cfg.Database.SQLitePath == "" {
		cfg.Database.SQLitePath = filepath.Join(cfg.DataDir, "aiterm.db")
	}

	if len(cfg.CORS.AllowedOrigins) == 0 {
		cfg.CORS.AllowedOrigins = defaultConfig().CORS.AllowedOrigins
	}

	if cfg.Log.RequestBody <= 0 {
		cfg.Log.RequestBody = defaultConfig().Log.RequestBody
	}

	if cfg.Log.ResponseBody <= 0 {
		cfg.Log.ResponseBody = defaultConfig().Log.ResponseBody
	}

	if cfg.LLM.ChatSystemPrompt == "" {
		cfg.LLM.ChatSystemPrompt = defaultConfig().LLM.ChatSystemPrompt
	}

	if cfg.LLM.TaskPlannerPrompt == "" {
		cfg.LLM.TaskPlannerPrompt = defaultConfig().LLM.TaskPlannerPrompt
	}

	if cfg.LLM.TaskPlannerUserPrompt == "" {
		cfg.LLM.TaskPlannerUserPrompt = defaultConfig().LLM.TaskPlannerUserPrompt
	}

	if cfg.LLM.TaskWindowsToolPrompt == "" {
		cfg.LLM.TaskWindowsToolPrompt = defaultConfig().LLM.TaskWindowsToolPrompt
	}

	if cfg.LLM.TaskLinuxToolPrompt == "" {
		cfg.LLM.TaskLinuxToolPrompt = defaultConfig().LLM.TaskLinuxToolPrompt
	}

	if cfg.LLM.TaskMacToolPrompt == "" {
		cfg.LLM.TaskMacToolPrompt = defaultConfig().LLM.TaskMacToolPrompt
	}

	if cfg.LLM.TaskFailureRepairPrompt == "" {
		cfg.LLM.TaskFailureRepairPrompt = defaultConfig().LLM.TaskFailureRepairPrompt
	}

	if cfg.LLM.TaskCommandRulesPrompt == "" {
		cfg.LLM.TaskCommandRulesPrompt = defaultConfig().LLM.TaskCommandRulesPrompt
	}

	if cfg.LLM.TaskCommandBlacklist == nil {
		cfg.LLM.TaskCommandBlacklist = defaultConfig().LLM.TaskCommandBlacklist
	}

	if cfg.LLM.TaskCommandWhitelist == nil {
		cfg.LLM.TaskCommandWhitelist = defaultConfig().LLM.TaskCommandWhitelist
	}
}
