# AITerm

[中文](README.md) | [English](README_en.md)

AI-powered intelligent terminal management tool for remote server management through natural language commands.

### Highlights

See the complete <a href="#task-test" style="color: skyblue;">task test</a> process for demonstration.

## Introduction

In daily server operations, administrators often need to manually enter numerous commands. AITerm aims to automate these tasks through natural language interaction, improving operational efficiency.

While tools like Claude Code, Openclaw, OpenCode, and Codex exist, AITerm focuses on:

- **Quick Deployment** - One-click startup, no complex configuration required
- **Simple Model Configuration** - Supports OpenAI-compatible APIs with intuitive configuration
- **Customizable Prompts** - System prompts are fully customizable
- **Multi-platform Access** - Web architecture accessible from both PC and mobile devices

> This system is developed and tested with DeepSeek official API, supporting `/chat/completions` endpoint, compatible with OpenAI API format.

## Features

- **Natural Language Interaction** - Describe tasks in natural language, AI automatically plans and executes
- **Multi-node Management** - Manage multiple servers with unified scheduling
- **Intelligent Command Generation** - AI generates commands adapted to target systems
- **Risk Assessment** - High-risk commands are automatically identified and require manual confirmation
- **Real-time Execution Feedback** - SSE streaming output of command execution process
- **Cross-platform Support** - Compatible with Windows, Linux, macOS
- **Tool System** - Support for custom tools, LLM can call tools to obtain information

## Interface Showcase

### Chat Interface

![Chat Interface](assets/对话.jpg)

Natural language interaction interface with AI displaying thinking process and tool calls in real-time.

### Chat History

![Chat History](assets/对话历史.jpg)

View historical conversation records, support continuing conversations and regeneration.

### Terminal Interface

![Terminal Interface](assets/终端.jpg)

Execute commands directly in the terminal with real-time result viewing.

### Node Management

![Node Management](assets/节点.jpg)

Manage multiple server nodes with support for adding, editing, and deleting nodes.

## Tech Stack

### Backend

- Python 3.10+ / FastAPI
- SQLite
- OpenAI-compatible API

### Frontend

- Vue 3 + TypeScript
- Element Plus
- xterm.js
- CodeMirror 6

## Quick Start

### Requirements

- Python 3.10+
- Node.js 18+

### Backend Startup

```bash
cd backend
pip install -r requirements.txt
python main.py
```

The service runs at `http://localhost:18084` by default.

#### Database Configuration

Configure database type (sqlite/mysql) in backend/app/configs/app.json.
The system automatically creates tables and fields.
For SQLite, the default path is backend/data/aiterm.db.

To use MySQL:

1. Copy the configuration template:

```bash
cd backend/configs
cp app.json.bak app.json
```

2. Edit `app.json` with your database configuration:

```json
{
  "database": {
    "driver": "mysql",
    "mysql_host": "your_mysql_host",
    "mysql_port": 3306,
    "mysql_user": "your_username",
    "mysql_password": "your_password",
    "mysql_database": "aiterm"
  }
}
```

### Frontend Startup

```bash
cd frontend
yarn install
yarn dev
```

The frontend development server runs at `http://localhost:18085` by default.

### Production Deployment

```bash
# Build frontend, automatically outputs to backend/dist directory
cd frontend
yarn build

# Start backend, access http://localhost:18084 to view the frontend
cd ../backend
python main.py
```

## Tool System

### Initialize Default Settings

Automatically initialize system prompts, history limits, tool call limits, command blacklist/whitelist, sandbox paths, etc.

```bash
python init_scripts/init_settings.py
```

### Initialize Default Tools

Click [Import Built-in Tools] on the tools page to select and import needed tools.

Preset tools include:

| Tool Name        | Display Name        | Description                                           |
| ---------------- | ------------------- | ----------------------------------------------------- |
| get_current_time | Get Current Time    | Get current date, time and day of week               |
| read_file        | Read File           | Read file content at specified path                   |
| write_file       | Write File          | Write content to file at specified path               |
| list_directory   | List Directory      | List files and subdirectories in specified directory  |
| delete_file      | Delete File         | Delete specified file                                 |
| copy_file        | Copy File           | Copy file to specified path                           |
| move_file        | Move File           | Move or rename file                                   |
| http_request     | HTTP Request        | Send HTTP requests, supports GET, POST, etc.          |
| download_file    | Download File       | Download file from URL to local                       |
| create_directory | Create Directory    | Create directory, supports multi-level creation        |
| get_file_info    | Get File Info       | Get detailed file info including size, modified time   |
| search_files     | Search Files        | Search matching files in directory                    |

And 40+ more tools.

### Tool Management

![Tool List](assets/工具列表.jpg)

View all available tools, support enabling/disabling tools.

![Tool Edit](assets/工具编辑.jpg)

Customize tool configuration including name, description, parameter definitions, and execution code.

### Tool Call Flow

```
User Message → LLM → Determine if tool call needed
                          ↓
              Return tool_calls (tool name + parameters)
                          ↓
              System executes tool code → Return result
                          ↓
              Result returned to LLM → Generate final response
```

## Conversation Flow

### Message Display Structure

During conversation, messages are displayed in the following order:

````
┌─────────────────────────────────────────────────────────────┐
│  User Input                                                 │
│  "Write an HTTP Python server file and save it"             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  🧠 Thinking... (Real-time display)                         │
│  ├─ User wants to create an HTTP server file...             │
│  ├─ I need to check current directory structure first...    │
│  └─ Then create a simple HTTP server code...                │
│                                                             │
│  ✅ Thought (2.3s) [Expand/Collapse]                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  🔧 Tool Call: list_directory (2024-01-15 10:30:15)         │
│  ├─ Parameters: {"path": "/data/sandbox"}                   │
│  └─ Result: {"files": ["test.py", "data.json"]}            │
│                                                             │
│  🔧 Tool Call: write_file (2024-01-15 10:30:18)             │
│  ├─ Parameters: {"path": "/data/sandbox/http_server.py"...} │
│  └─ Result: {"success": true}                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  💬 AI Response                                             │
│  I've created a simple HTTP server file `http_server.py`    │
│  saved in the sandbox directory. You can run it with:       │
│                                                             │
│  ```bash                                                    │
│  python http_server.py                                      │
│  ```                                                        │
└─────────────────────────────────────────────────────────────┘
````

### Multi-round Tool Calls

For complex tasks, the LLM may perform multiple rounds of thinking and tool calls:

```
Input → Thinking1 → ToolCall1 → Thinking2 → ToolCall2 → ... → Response
```

Example flow:

| Step | Type     | Description                                    |
| ---- | -------- | ---------------------------------------------- |
| 1    | Input    | User sends message                             |
| 2    | Thinking | LLM analyzes task, plans execution steps       |
| 3    | Tool     | Call `list_directory` to view directory        |
| 4    | Thinking | Decide next action based on directory content  |
| 5    | Tool     | Call `write_file` to create file               |
| 6    | Thinking | Confirm file creation success, prepare answer  |
| 7    | Response | Generate final reply                           |

### Real-time Display Features

- **Real-time Streaming of Thinking Process** - Users can see LLM's thinking process
- **Instant Tool Call Feedback** - Display tool name, parameters, and execution results
- **Timestamp Information** - Each thinking phase and tool call shows timestamp
- **Independent Expand Control** - Thinking and tool call areas can be expanded/collapsed independently

### Configuration Options

Configure in global settings:

| Option              | Description                                         |
| ------------------- | --------------------------------------------------- |
| Show Chat Input     | Whether to display input content for each LLM call  |
| Max Iterations      | Maximum loop count for tool calls (default 20)      |
| Sandbox Path        | Allowed path range for file operations              |

#### Model Configuration

![Model Configuration](assets/模型配置.jpg)

Configure LLM API, supports OpenAI-compatible API interfaces.

#### Global Configuration

![Global Configuration](assets/全局配置.jpg)

System global settings including prompt templates, sandbox paths, iteration limits, etc.

#### User Configuration

![User Configuration](assets/用户配置.jpg)

User personal settings including theme, language, and other preferences.

### Custom Tools

Tool code needs to define an `execute` function:

```python
def execute(arguments):
    """
    arguments: dict - Tool parameters
    Returns: Tool execution result
    """
    # Write your tool logic here
    return {"success": True, "result": "..."}
```

## Usage Examples

1. Access the Web interface and configure LLM API
2. Enter natural language commands in the chat interface, such as:
   - "Check system memory usage"
   - "Install nginx and configure reverse proxy"
   - "Check disk space and clean temporary files"
3. AI automatically generates command plan, execute after confirmation
4. View execution results in real-time

## Project Structure

```
AITerm/
├── backend/               # Backend service
│   ├── app/               # Application module
│   │   ├── api/           # API routes
│   │   ├── db/            # Database models
│   │   ├── models/        # Pydantic models
│   │   ├── repositories/  # Data access layer
│   │   └── services/      # Business logic layer
│   ├── init_scripts/      # Initialization scripts
│   ├── dist/              # Frontend build output (auto-generated)
│   └── main.py            # Entry file
├── frontend/              # Frontend application
│   ├── src/               # Source code
│   └── public/            # Static assets
├── assets/                # Documentation images
└── README.md
```

## Complete Conversation Example

The following shows a complete conversation example from user input to AI response:

![Complete Conversation Process](assets/对话完整过程.png)

### Conversation Flow Description

User request: "Write an HTTP Python code file and save it"

**Iteration 1:**

| Phase     | Content                                                              |
| --------- | -------------------------------------------------------------------- |
| Thinking  | Analyze user requirements, decide to check sandbox directory first   |
| Tool Call | `list_directory` - View directory `I:/sandbox`                       |
| Result    | Found `flask_app`, `http_server.py`, `main.py` in directory          |

**Iteration 2:**

| Phase     | Content                                                  |
| --------- | -------------------------------------------------------- |
| Thinking  | Decide to create a new comprehensive HTTP demo file      |
| Tool Call | `write_file` - Write complete HTTP server code           |
| Result    | Successfully created 6.6 KB Python file                  |

**Iteration 3:**

| Phase     | Content                              |
| --------- | ------------------------------------ |
| Thinking  | Verify if file was created successfully |
| Tool Call | `get_file_info` - Get file info      |
| Result    | Confirmed file creation, show details |

**Final Response:**

AI returned a summary of successful file creation, including file path, size, creation time, and file content description with usage instructions.

## Task Test <a id="task-test"></a>

### Task Test Script

![Task Test Script](assets/任务测试脚本.png)

### Task Test Results

![Task Test Results](assets/任务测试结果.png)

### Task Test Complete Process (including thinking, tool calls, and response process - input content too long to display)

![Task Test Flow](assets/任务测试流程.png)
