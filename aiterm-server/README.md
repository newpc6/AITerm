# aiterm-server

Go backend service for AITerm.

## 启动方式

默认读取 `configs/app.json`，推荐通过配置文件管理端口、数据库和跨域白名单。

当前默认配置：

- 后端端口：`8080`
- 数据库驱动：`sqlite`
- SQLite 文件：`data/aiterm.db`
- 允许的前端来源：
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`

启动命令：

```bash
go run ./cmd/aiterm-server
```

启动后终端会打印监听地址和数据库信息，例如：

```text
AITerm server listening on http://127.0.0.1:8080 (db=sqlite, sqlite=data/aiterm.db)
```

## 配置文件

配置文件路径：

```text
configs/app.json
```

示例：

```json
{
  "port": 8080,
  "data_dir": "data",
  "database": {
    "driver": "sqlite",
    "sqlite_path": "data/aiterm.db",
    "mysql_dsn": ""
  },
  "cors": {
    "allowed_origins": [
      "http://localhost:5173",
      "http://127.0.0.1:5173"
    ]
  }
}
```

说明：

- 默认数据库使用 `sqlite`
- 可将 `driver` 改为 `mysql`，但当前 `mysql` 存储层尚未实现
- `allowed_origins` 需要包含你的前端调试地址，否则浏览器会触发跨域拦截
