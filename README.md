# Coze FastAPI Service

Coze API 服务，使用 FastAPI 框架和异步结构实现。

## 项目结构

```
coze_fastapi/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── models.py               # 数据模型
│   ├── redis_client.py         # Redis 客户端（异步）
│   ├── tasks.py                # 异步任务处理
│   ├── routes.py               # FastAPI 路由
│   ├── auth.py                 # 认证中间件
│   ├── exceptions.py           # 异常定义
│   ├── error_handlers.py       # 错误处理
│   ├── utils.py                # 工具函数
│   └── logging_config.py       # 日志配置
├── Dockerfile                  # 容器构建文件
├── podman-build.sh             # 构建脚本
├── podman-run.sh               # 运行脚本
├── podman-compose_dev.yml      # 开发环境配置
├── pyproject.toml              # 依赖管理（uv）
└── README.md                   # 项目文档
```

## 特性

- 使用 FastAPI 框架，支持异步处理
- 与 `ai-api` 的 Coze 模块统一的数据结构与响应格式
- 使用 uv 管理 Python 依赖
- 容器内端口固定为 6000，主机端口可配置
- 保持与原有接口的兼容性（`/coze/*` 路径）
- 支持认证验证（可通过环境变量禁用）
- 异步 Redis 客户端与 Coze API 调度，可同时处理多用户会话
- 完整的错误处理和日志记录

## 快速开始

### 1. 环境配置

设置环境变量：

```bash
# Coze API配置
export COZE_API_URL=https://api.coze.cn/v3/chat
export COZE_AUTHORIZATION=Bearer your_token_here
export COZE_BOT_ID=your_bot_id

# Redis配置
export REDIS_URL=redis://localhost:6379/0

# 认证配置
export ENABLE_AUTH=true
export HTTP_SCHEME=https://
export ALCHEMY_HOST=alchemy-studio.cn
export MOICEN_HOST=moicen.com
export HUIWINGS_HOST=huiwings.cn
export LOCAL_HOST=localhost

# 其余可选项参考 app/config.py
```

> 提示：未设置 `COZE_API_URL/COZE_BASE_URL` 时，`app/config.py` 会在 `APP_MODE=remote` 下默认连官方云 `https://api.coze.cn/v3/chat`；`APP_MODE=local` 时则回落到 `http://localhost:5000/coze/v3/chat`，与 `ai-api` 行为一致。

### 2. 运行脚本（推荐）

完整运行流程与 `ai-api` 保持相同，包含 Redis、FastAPI、日志三个 tmux 面板：

```bash
# 远程模式（默认、启用认证、Host 0.0.0.0）
./run-service.sh deployment

# 本地测试模式（禁用认证、Host 0.0.0.0，用于调试）
./run-service.sh test
```

脚本会导出 `APP_MODE/ENABLE_AUTH/COZE_API_URL/...` 供 FastAPI 读取，并在启动后自动进行健康检查。

### 3. 本地开发（手动）

```bash
# 安装依赖（使用 uv）
uv sync

# 运行服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 6000 --reload
```

### 4. 容器化部署

```bash
# 构建镜像
./podman-build.sh

# 运行容器（默认端口 6000）
./podman-run.sh

# 运行容器（指定端口）
./podman-run.sh 6001

# 停止容器
./podman-run.sh stop

# 进入容器
./podman-run.sh enter
```

## API 接口

所有接口路径保持与原有系统一致：`/coze/*`

### 健康检查

```http
GET /coze/health
```

### 创建会话

```http
POST /coze/sessions
Content-Type: application/json

{
  "user_id": "user123",
  "bot_id": "bot456",
  "additional_messages": [],
  "auto_save_history": true,
  "meta_data": {}
}
```

### 发送消息

```http
POST /coze/sessions/{session_id}/messages
Content-Type: application/json

{
  "message": "Hello, how are you?",
  "stream": false
}
```

### 获取聊天结果

```http
GET /coze/chats/{chat_id}/result
```

### 获取会话信息

```http
GET /coze/sessions/{session_id}
```

### 终止会话

```http
DELETE /coze/sessions/{session_id}
```

> 所有接口返回体中的 `data.task_result` 与 `ai-api` 完全一致：会再嵌套一层 `success/timestamp/data`，需要的 `session_id` 等字段位于 `task_result.data.session_id`。

## 配置说明

### 端口配置

- 容器内端口：固定为 6000
- 主机端口：可通过 `HOST_PORT` 环境变量或 `podman-run.sh` 参数配置，默认 6000

### 认证配置

- `ENABLE_AUTH`: 是否启用认证（默认：true）
- 认证通过 `HtySudoerToken` 和 `HtyHost` 请求头进行验证

### 并发说明

- FastAPI 路由、Redis 客户端、Coze API 调用均为异步实现，可同时处理多个会话/消息请求
- 若需要更高吞吐，可在 `run-service.sh` 中自定义 `uvicorn` worker/loop 参数或部署多个容器实例

## 技术栈

- FastAPI: Web 框架
- uvicorn: ASGI 服务器
- httpx: 异步 HTTP 客户端
- redis: 异步 Redis 客户端
- loguru: 日志记录
- uv: Python 包管理器

## 开发说明

项目使用 uv 管理依赖，所有 Python 包通过 `pyproject.toml` 定义。

构建容器时会自动安装 uv 和所有依赖。
