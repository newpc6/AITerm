# AITerm

AI 驱动的智能终端管理工具，通过自然语言指令远程管理服务器。

## 功能特性

- **自然语言交互** - 用自然语言描述任务，AI 自动规划并执行
- **多节点管理** - 支持管理多台服务器，统一调度执行
- **智能命令生成** - AI 自动生成适配目标系统的命令
- **风险评估** - 高风险命令自动识别，需人工确认后执行
- **实时执行反馈** - SSE 流式输出命令执行过程
- **跨平台支持** - 兼容 Windows、Linux、macOS

## 技术栈

### 后端

- Go 1.26+
- SQLite / MySQL
- OpenAI 兼容 API

### 前端

- Vue 3 + TypeScript
- Element Plus
- xterm.js

## 快速开始

### 环境要求

- Go 1.26+
- Node.js 18+
- Yarn

### 后端启动

```bash
cd aiterm-server
go build ./...
go run ./cmd/aiterm-server
拷贝configs下的app.jsoncopy到app.json
```

服务默认运行在 `http://localhost:18084`

### 前端启动

```bash
cd aiterm-web
yarn install
yarn dev
```

前端开发服务器默认运行在 `http://localhost:5173`

## 配置

配置文件位于 `aiterm-server/configs/app.json`：

```json
{
  "server": {
    "port": 18084
  },
  "database": {
    "driver": "sqlite",
    "dsn": "data/aiterm.db"
  },
  "llm": {
    "api_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "temperature": 0.7
  }
}
```

## 使用示例

1. 访问 Web 界面，配置 LLM API
2. 在聊天界面输入自然语言指令，如：
   - "查看系统内存使用情况"
   - "安装 nginx 并配置反向代理"
   - "检查磁盘空间并清理临时文件"
3. AI 自动生成命令计划，确认后执行
4. 实时查看执行结果

## 项目结构

```
AITerm/
├── aiterm-server/     # 后端服务
│   ├── cmd/           # 入口
│   ├── internal/      # 内部模块
│   └── configs/       # 配置文件
├── aiterm-web/        # 前端应用
│   ├── src/           # 源代码
│   └── public/        # 静态资源
└── .gitignore
```

## License

MIT
