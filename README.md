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
├── .env.example                # 环境变量模板文件
├── .env                        # 环境变量文件（本地，不提交到 Git）
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
- **安全的敏感信息管理**：使用 `.env` 文件管理敏感配置，不将敏感信息提交到代码仓库

## 快速开始

### 1. 环境配置

#### 使用 .env 文件（推荐）

项目使用 `.env` 文件管理敏感信息和配置。首次使用需要创建 `.env` 文件：

```bash
# 从模板复制
cp .env.example .env

# 编辑 .env 文件，填写必填的敏感信息
# 必填项：
#   - COZE_API_TOKEN: Coze API Token
#   - COZE_BOT_ID: Coze Bot ID
```

`.env` 文件示例：

```bash
# 必填：Coze API Token（从 Coze 平台获取）
COZE_API_TOKEN=your_coze_api_token_here

# 必填：Coze Bot ID
COZE_BOT_ID=your_bot_id_here

# 可选配置（有默认值，可根据需要取消注释修改）
# COZE_API_URL=https://api.coze.cn/v3/chat
# REDIS_URL=redis://localhost:6379/0
# ENABLE_AUTH=true
# ... 更多配置项参考 .env.example
```

> **安全提示**：
> - `.env` 文件已在 `.gitignore` 中，不会被提交到 Git
> - 请勿将 `.env` 文件提交到版本控制系统
> - 生产环境建议使用密钥管理服务（如 Kubernetes Secrets、HashiCorp Vault）

#### 使用环境变量（备选）

也可以直接设置环境变量（不推荐用于敏感信息）：

```bash
export COZE_API_TOKEN=your_token_here
export COZE_BOT_ID=your_bot_id
# ... 其他环境变量
```

> 提示：未设置 `COZE_API_URL/COZE_BASE_URL` 时，`app/config.py` 会在 `APP_MODE=remote` 下默认连官方云 `https://api.coze.cn/v3/chat`；`APP_MODE=local` 时则回落到 `http://localhost:5000/coze/v3/chat`，与 `ai-api` 行为一致。

### 2. 从零开始完整部署流程

#### 2.1 克隆项目并初始化

```bash
# 1. 克隆项目（如果还没有）
git clone <repository-url>
cd coze_fastapi

# 2. 创建 .env 文件并配置敏感信息
cp .env.example .env
# 编辑 .env 文件，填写必填项：
#   - COZE_API_TOKEN: 你的 Coze API Token
#   - COZE_BOT_ID: 你的 Coze Bot ID

# 3. 安装依赖（本地开发需要）
# 如果使用容器部署，可以跳过此步骤
uv sync
```

#### 2.2 运行模式说明

项目支持两种运行模式，通过 `run-service.sh` 脚本的参数选择：

**test 模式（本地测试模式）**
- **用途**：本地开发和调试
- **认证**：禁用认证（`ENABLE_AUTH=false`），方便本地测试，无需 JWT Token
- **API 模式**：本地模式（`APP_MODE=local`），连接到 `http://localhost:5000/coze/v3/chat`
- **日志级别**：DEBUG，输出详细调试信息
- **适用场景**：
  - 本地开发调试
  - 快速测试 API 功能
  - 不需要认证验证的场景

**deployment 模式（远程部署模式）**
- **用途**：生产环境或远程部署
- **认证**：启用认证（`ENABLE_AUTH=true`），需要有效的 JWT Token 才能访问接口
- **API 模式**：远程模式（`APP_MODE=remote`），连接到 `https://api.coze.cn/v3/chat`
- **日志级别**：INFO，只输出重要信息
- **适用场景**：
  - 生产环境部署
  - 远程服务器部署
  - 需要安全认证的场景

#### 2.3 本地运行（不使用容器）

**方式一：使用运行脚本（推荐）**

脚本会自动启动 Redis、FastAPI 服务和日志监控，使用 tmux 管理多个面板：

```bash
# 部署模式（生产环境，启用认证）
./run-service.sh deployment

# 测试模式（本地开发，禁用认证）
./run-service.sh test
```

**脚本功能说明**：
- 自动启动 Redis 服务器（如果未运行）
- 启动 FastAPI 服务（使用 uvicorn）
- 启动日志监控面板
- 自动进行健康检查
- 使用 tmux 管理多个终端面板

**方式二：手动启动（适合调试）**

```bash
# 1. 确保 Redis 运行
redis-server --port 6379

# 2. 安装依赖
uv sync

# 3. 运行服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 6000 --reload
```

### 3. 容器化部署（推荐用于开发和生产）

#### 3.1 完整容器化部署流程

**步骤 1：准备环境配置文件**

```bash
# 确保已创建并配置 .env 文件
cp .env.example .env
# 编辑 .env 文件，填写真实的 COZE_API_TOKEN 和 COZE_BOT_ID
```

**步骤 2：构建容器镜像**

```bash
# 构建 Docker/Podman 镜像
# 这会安装所有依赖并准备运行环境
./podman-build.sh
```

构建过程包括：
- 安装系统依赖（Python、Redis 等）
- 安装 uv 包管理器
- 安装 Python 依赖（从 `pyproject.toml`）
- 配置运行环境

**步骤 3：启动容器**

```bash
# 启动容器（默认端口 6000）
# 容器会通过 Volume 挂载访问项目目录和 .env 文件
./podman-run.sh

# 或指定自定义端口
./podman-run.sh 6001
```

**步骤 4：进入容器并启动服务**

容器启动后，默认只保持运行状态，需要手动进入容器启动服务：

```bash
# 进入容器
./podman-run.sh enter

# 在容器内，你可以选择以下方式之一启动服务：

# 方式 1：使用运行脚本（推荐，自动管理 Redis、FastAPI、日志）
./run-service.sh deployment  # 或 ./run-service.sh test

# 方式 2：手动启动（适合调试）
# 1. 启动 Redis（如果容器内没有运行）
redis-server --daemonize yes

# 2. 启动 FastAPI 服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 6000

# 方式 3：使用后台运行
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 6000 > /tmp/coze.log 2>&1 &
```

**步骤 5：验证服务运行**

```bash
# 在容器内或宿主机上测试
curl http://localhost:6000/coze/health

# 或从宿主机访问（如果端口已映射）
curl http://localhost:6000/coze/health
```

#### 3.2 容器管理命令

```bash
# 停止容器
./podman-run.sh stop

# 重启容器
./podman-run.sh restart

# 进入运行中的容器
./podman-run.sh enter

# 查看容器状态
podman ps -a | grep coze-fastapi
```

#### 3.3 容器化部署说明

**Volume 挂载方案**：
- 使用 `podman-compose_dev.yml` 中的 `.:/coze-fastapi:Z` 配置
- 整个项目目录（包括 `.env` 文件）会挂载到容器的 `/coze-fastapi` 目录
- 修改 `.env` 文件后，容器内立即生效，无需重建镜像
- 代码修改也会实时反映到容器中

**服务运行位置**：
- **服务在容器内运行**：FastAPI 服务运行在容器内部
- **端口映射**：容器内的 6000 端口映射到宿主机的指定端口（默认 6000）
- **数据持久化**：Redis 数据存储在容器内（如需持久化，可配置 Volume）

**开发工作流**：
1. 在宿主机上编辑代码和 `.env` 文件
2. 进入容器启动服务
3. 修改会通过 Volume 挂载自动同步到容器
4. 重启服务即可看到更改（或使用 `--reload` 自动重载）

#### 3.4 生产环境部署建议

生产环境建议使用以下方式之一：

1. **环境变量传递**：通过容器编排工具（如 Kubernetes）的 Secrets 传递环境变量
   ```yaml
   # Kubernetes 示例
   env:
     - name: COZE_API_TOKEN
       valueFrom:
         secretKeyRef:
           name: coze-secrets
           key: api-token
   ```

2. **密钥管理服务**：使用 AWS Secrets Manager、HashiCorp Vault 等
   - 避免将敏感信息存储在文件中
   - 支持密钥轮换和审计

3. **env_file 配置**：在 `podman-compose` 中使用 `env_file` 配置
   ```yaml
   services:
     coze-fastapi:
       env_file:
         - .env.production  # 确保此文件安全存储
   ```

4. **只读 Volume 挂载**：生产环境建议使用只读挂载，避免意外修改

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

### 配置文件

项目支持两种配置方式（按优先级排序）：

1. **环境变量**：直接设置的环境变量（优先级最高）
2. **.env 文件**：项目根目录的 `.env` 文件（推荐用于敏感信息）

配置加载顺序：
- 应用启动时自动加载 `.env` 文件（通过 `python-dotenv`）
- 环境变量会覆盖 `.env` 文件中的同名配置

### 必填配置项

以下配置项必须设置（通过 `.env` 文件或环境变量）：

- `COZE_API_TOKEN`: Coze API Token（必填）
- `COZE_BOT_ID`: Coze Bot ID（必填）

### 可选配置项

所有可选配置项都有默认值，可在 `.env.example` 中查看完整列表，主要包括：

- `COZE_API_URL`: Coze API URL（默认：`https://api.coze.cn/v3/chat`）
- `REDIS_URL`: Redis 连接 URL（默认：`redis://localhost:6379/0`）
- `ENABLE_AUTH`: 是否启用认证（默认：`true`）
- `APP_MODE`: 应用模式，`remote` 或 `local`（默认：`remote`）
- 更多配置项参考 `.env.example` 文件

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
- python-dotenv: 环境变量管理

## 安全注意事项

### 敏感信息管理

1. **不要提交敏感信息到代码仓库**
   - `.env` 文件已在 `.gitignore` 中
   - 确保敏感信息（Token、密钥等）只存在于 `.env` 文件中

2. **.env 文件权限**
   - 建议设置文件权限：`chmod 600 .env`
   - 仅项目维护者可以访问

3. **生产环境建议**
   - 使用密钥管理服务（Kubernetes Secrets、AWS Secrets Manager 等）
   - 通过环境变量传递，而不是文件挂载
   - 定期轮换 API Token

4. **代码审查**
   - 确保代码中没有硬编码的敏感信息
   - 使用 `.env.example` 作为配置模板

### 验证配置

启动前可以验证配置是否正确：

```bash
# 验证 .env 文件加载
uv run python -c "from app.config import get_coze_config; config = get_coze_config(); print('Bot ID:', config.bot_id)"
```

## 开发说明

项目使用 uv 管理依赖，所有 Python 包通过 `pyproject.toml` 定义。

构建容器时会自动安装 uv 和所有依赖。

### 依赖更新

```bash
# 同步依赖
uv sync

# 添加新依赖
uv add package_name

# 更新依赖
uv lock --upgrade
```
