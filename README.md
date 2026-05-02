# AITerm

AI 驱动的智能终端管理工具，通过自然语言指令远程管理服务器。

## 功能特性

- **自然语言交互** - 用自然语言描述任务，AI 自动规划并执行
- **多节点管理** - 支持管理多台服务器，统一调度执行
- **智能命令生成** - AI 自动生成适配目标系统的命令
- **风险评估** - 高风险命令自动识别，需人工确认后执行
- **实时执行反馈** - SSE 流式输出命令执行过程
- **跨平台支持** - 兼容 Windows、Linux、macOS
- **工具系统** - 支持自定义工具，大模型可调用工具获取信息

## 技术栈

### 后端

- Python 3.10+ / FastAPI
- SQLite
- OpenAI 兼容 API

### 前端

- Vue 3 + TypeScript
- Element Plus
- xterm.js
- CodeMirror 6

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### 后端启动

```bash
cd aiterm-server-python
pip install -r requirements.txt
python main.py
```

服务默认运行在 `http://localhost:18085`

### 前端启动

```bash
cd aiterm-web
yarn install
yarn dev
```

前端开发服务器默认运行在 `http://localhost:5173`

## 工具系统

### 初始化默认工具

运行以下脚本导入预设工具：

```bash
cd aiterm-server-python
python init_scripts/init_tools.py
```

预设工具包括：

| 工具名称         | 显示名称     | 描述                                     |
| ---------------- | ------------ | ---------------------------------------- |
| get_current_time | 获取当前时间 | 获取当前日期、时间和星期                 |
| read_file        | 读取文件     | 读取指定路径的文件内容                   |
| write_file       | 写入文件     | 将内容写入指定路径的文件                 |
| list_directory   | 列出目录     | 列出指定目录下的文件和子目录             |
| delete_file      | 删除文件     | 删除指定的文件                           |
| copy_file        | 复制文件     | 复制文件到指定路径                       |
| move_file        | 移动文件     | 移动或重命名文件                         |
| http_request     | HTTP请求     | 发送HTTP请求，支持GET、POST等方法        |
| download_file    | 下载文件     | 从URL下载文件到本地                      |
| create_directory | 创建目录     | 创建目录，支持多级创建                   |
| get_file_info    | 获取文件信息 | 获取文件的详细信息，包括大小、修改时间等 |
| search_files     | 搜索文件     | 在目录中搜索匹配的文件                   |

### 工具调用流程

```
用户消息 → 大模型 → 判断是否需要调用工具
                          ↓
              返回 tool_calls（工具名+参数）
                          ↓
              系统执行工具代码 → 返回结果
                          ↓
              结果返回大模型 → 生成最终回复
```

### 自定义工具

工具代码需要定义 `execute` 函数：

```python
def execute(arguments):
    """
    arguments: dict - 工具参数
    返回: 工具执行结果
    """
    # 在这里编写你的工具逻辑
    return {"success": True, "result": "..."}
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
├── aiterm-server-python/  # 后端服务
│   ├── app/               # 应用模块
│   │   ├── api/           # API 路由
│   │   ├── db/            # 数据库模型
│   │   ├── models/        # Pydantic 模型
│   │   ├── repositories/  # 数据访问层
│   │   └── services/      # 业务逻辑层
│   ├── scripts/           # 脚本
│   │   └── init_tools.py  # 工具初始化脚本
│   └── main.py            # 入口文件
├── aiterm-web/            # 前端应用
│   ├── src/               # 源代码
│   └── public/            # 静态资源
└── README.md
```

## License

MIT
