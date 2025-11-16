#!/bin/bash

# Coze FastAPI 服务启动脚本
# 功能：使用全局Python环境，通过tmux启动FastAPI服务

# 注意：在清理阶段使用 set +e 允许命令失败
set -uo pipefail  # 不设置 -e，允许某些命令失败（如清理不存在的进程）

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 进程检查函数
check_process_cleanup() {
    local service_name=$1
    local check_command=$2
    
    # 执行检查命令，如果找到进程（命令成功），说明清理失败
    if eval "$check_command" &>/dev/null 2>&1; then
        log_warning "$service_name process still exists, but continuing..."
        return 1
    fi
    # 如果命令失败（找不到进程），说明清理成功
    return 0
}

# 确保uv在PATH中（使用uv run不需要手动设置Python PATH）
detect_and_activate_uv() {
    export PATH="/root/.local/bin:${PATH}"
    
    log_info "Ensuring uv is in PATH..."
    
    # 检查 uv 是否可用
    if ! command -v uv >/dev/null 2>&1; then
        log_warning "uv not found in /root/.local/bin"
        return 1
    fi
    
    # 使用 uv run 来检查 Python 环境
    if uv run python3 --version &>/dev/null; then
        PYTHON_VERSION=$(uv run python3 --version 2>&1)
        log_success "uv and Python available (version: $PYTHON_VERSION via uv run)"
        return 0
    else
        log_warning "uv run python3 not available"
        return 1
    fi
}

# Default parameters
MODE="remote"
ENABLE_AUTH="true"
LOG_LEVEL="INFO"
PORT=6000
HOST="0.0.0.0"

# Parse command line arguments
if [ $# -gt 0 ]; then
    case $1 in
        test)
            MODE="local"
            ENABLE_AUTH="false"
            LOG_LEVEL="DEBUG"
            HOST="127.0.0.1"
            log_info "Detected parameter: test - Switching to local test mode"
            ;;
        deployment)
            MODE="remote"
            ENABLE_AUTH="true"
            LOG_LEVEL="INFO"
            HOST="0.0.0.0"
            log_info "Detected parameter: deployment - Switching to remote deployment mode"
            ;;
        -h|--help)
            echo "Usage: $0 [test|deployment]"
            echo "  test: Local mode, disable authentication, DEBUG log level, listen on 127.0.0.1"
            echo "  deployment: Remote mode, enable authentication, INFO log level, listen on 0.0.0.0 (default)"
            echo "  no parameter: Default to remote mode, enable authentication, INFO log level"
            exit 0
            ;;
        *)
            echo "Unknown parameter: $1"
            echo "Use --help to view help information"
            exit 1
            ;;
    esac
else
    log_info "No parameter specified, using default configuration"
fi

# Display current configuration information
echo
log_info "=== Coze FastAPI Service Startup Configuration ==="
log_info "Starting Coze FastAPI service..."
log_info "Current working directory: $PWD"
log_info "Python environment: Global (uv managed)"
log_info "Redis connection: localhost:6379"
log_info "Running mode: $MODE"
log_info "Authentication: $([ "$ENABLE_AUTH" = "true" ] && echo "Enabled" || echo "Disabled")"
log_info "Log level: $LOG_LEVEL"
log_info "Service port: $PORT"
log_info "Service host: $HOST"
log_info "Configuration description:"
if [ "$MODE" = "local" ]; then
    echo "  - Local test mode: FastAPI service listens on 127.0.0.1, suitable for development debugging"
    echo "  - Authentication disabled: Skip JWT token verification, convenient for local testing"
    echo "  - DEBUG log level: Output detailed debug information for troubleshooting"
    echo "  - Recommended for: Development environment, functional testing, API debugging"
else
    echo "  - Remote deployment mode: FastAPI service listens on 0.0.0.0, suitable for production"
    echo "  - Authentication enabled: Valid JWT token required to access interfaces"
    echo "  - INFO log level: Output standard information logs, balance performance and observability"
    echo "  - Recommended for: Production environment, pre-release environment"
fi
echo "================================"
echo

# Error handling function
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Script execution failed, exit code: $exit_code"
        log_info "Cleaning up tmux sessions..."
        tmux kill-session -t coze-fastapi 2>/dev/null || true
    fi
    exit $exit_code
}

# Set error handling
trap cleanup EXIT

# Check if required commands exist
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Command '$1' not found, please install first"
        exit 1
    fi
}

# Check required commands
log_info "Checking required commands..."

# 确保uv和Python在PATH中（如果失败，继续执行，让后续check_command检查）
detect_and_activate_uv || log_warning "uv and Python path detection failed, will check commands individually"

check_command "tmux"
check_command "uv"
# 注意：不检查系统 python3，因为使用 uv run python3

# Check project directory
if [ ! -f "pyproject.toml" ]; then
    log_error "pyproject.toml file not found, please ensure you are running this script in the coze_fastapi project root directory"
    exit 1
fi

# 验证Python环境（使用uv管理的Python环境）
log_info "Verifying Python environment..."
PYTHON_VERSION=$(uv run python3 --version 2>&1)
PYTHON_EXE=$(uv run python3 -c 'import sys; print(sys.executable)' 2>&1)
PYTHON_SITE=$(uv run python3 -c 'import site; print(site.getsitepackages()[0])' 2>&1)
log_success "Python: $PYTHON_VERSION"
log_info "Python executable: $PYTHON_EXE"
log_info "Site-packages: $PYTHON_SITE"

# 验证关键依赖（使用uv管理的环境）
log_info "Verifying critical dependencies..."
if uv run python3 -c 'import fastapi, uvicorn, httpx, redis' 2>/dev/null; then
    log_success "Core dependencies verified"
else
    log_error "Core dependencies verification failed, please check Docker image build"
    uv run python3 -c 'import fastapi' 2>&1 || log_error "fastapi not available"
    uv run python3 -c 'import uvicorn' 2>&1 || log_error "uvicorn not available"
    uv run python3 -c 'import httpx' 2>&1 || log_error "httpx not available"
    uv run python3 -c 'import redis' 2>&1 || log_error "redis not available"
    exit 1
fi

log_success "All dependencies verified (using uv managed environment)"

# Note: Redis will be started in tmux, so we skip the connection check here
# Redis connection will be verified after it starts in tmux
log_info "Redis will be started in tmux session"

# Force cleanup of all related processes
log_info "Force cleaning up all related processes..."
set +e
# 直接使用 pkill，参考 ai-api 的方式，避免管道问题
# 使用精确的匹配模式，避免误杀脚本本身
pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
pkill -9 -f "redis-server" 2>/dev/null || true
set -e
sleep 3

# Check and close previous services
log_info "Checking and closing previous services..."

# Check and stop Redis service
set +e
if pgrep -f "redis-server" &>/dev/null; then
    log_warning "Detected Redis service, stopping..."
    REDIS_PIDS=$(pgrep -f "redis-server" 2>/dev/null || echo "")
    if [ -n "$REDIS_PIDS" ]; then
        log_info "Found Redis processes: $REDIS_PIDS"
        redis-cli shutdown 2>/dev/null || true
        sleep 2
        for i in {1..3}; do
            if ! pgrep -f "redis-server" &>/dev/null; then
                break
            fi
            log_warning "Redis stop retry $i/3"
            redis-cli shutdown 2>/dev/null || true
            sleep 2
        done
        if pgrep -f "redis-server" &>/dev/null; then
            log_warning "Redis failed to shut down gracefully, force stopping..."
            pkill -9 -f "redis-server" 2>/dev/null || true
            sleep 2
        fi
    fi
fi

# Check and stop FastAPI service
if pgrep -f "uvicorn.*app.main:app" &>/dev/null; then
    log_warning "Detected FastAPI service, stopping..."
    FASTAPI_PIDS=$(pgrep -f "uvicorn.*app.main:app" 2>/dev/null || echo "")
    if [ -n "$FASTAPI_PIDS" ]; then
        log_info "Found FastAPI processes: $FASTAPI_PIDS"
        # 先尝试优雅关闭
        echo "$FASTAPI_PIDS" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        if pgrep -f "uvicorn.*app.main:app" &>/dev/null; then
            log_warning "FastAPI processes failed to stop gracefully, force terminating..."
            pkill -9 -f "uvicorn.*app.main:app" 2>/dev/null || true
            sleep 2
        fi
    fi
fi

# 检查端口占用
if lsof -i :6379 &>/dev/null 2>&1; then
    log_warning "Port 6379 is still in use, force stopping..."
    lsof -ti :6379 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 1
fi

if lsof -i :${PORT} &>/dev/null 2>&1; then
    log_warning "Port ${PORT} is still in use, force stopping..."
    lsof -ti :${PORT} 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 1
fi
set -e

# Clean up existing tmux sessions
log_info "Cleaning up existing tmux sessions..."
set +e
if tmux has-session -t coze-fastapi 2>/dev/null; then
    log_warning "Found existing coze-fastapi session, closing..."
    tmux kill-session -t coze-fastapi 2>/dev/null || true
    sleep 1
fi
set -e

# Wait for all processes to stop completely
log_info "Waiting for all processes to stop completely..."
sleep 2

# Verify cleanup results (简化验证，不强制退出)
log_info "Verifying service cleanup status..."
set +e
if pgrep -f "redis-server" &>/dev/null; then
    log_warning "Redis process may still be running, but continuing..."
fi

if pgrep -f "uvicorn.*app.main:app" &>/dev/null; then
    log_warning "FastAPI process may still be running, but continuing..."
fi
set -e

log_success "Service cleanup completed"

# Create new tmux session
log_info "Creating tmux session 'coze-fastapi'..."
tmux new-session -d -s coze-fastapi || {
    log_error "Unable to create tmux session"
    exit 1
}

# Rename window
tmux rename-window -t coze-fastapi:0 'service' || {
    log_error "Unable to rename tmux window"
    exit 1
}

# Create three panel layout (3 rows, 1 column)
log_info "Creating service panels..."
tmux split-window -v -t coze-fastapi:service || {
    log_error "Unable to create second panel"
    exit 1
}

tmux split-window -v -t coze-fastapi:service.1 || {
    log_error "Unable to create third panel"
    exit 1
}

# Adjust panel layout to vertical even distribution
tmux select-layout -t coze-fastapi:service even-vertical || {
    log_error "Unable to set panel layout"
    exit 1
}

# Start Redis server in panel 0
log_info "Starting Redis server..."

# Decide whether to clean Redis data based on environment
if [ "$MODE" = "local" ]; then
    log_info "Development environment: Cleaning Redis data files to avoid format conflicts"
    REDIS_CLEANUP_CMD="rm -f /coze-fastapi/dump.rdb /tmp/dump.rdb /tmp/redis.log 2>/dev/null; "
else
    log_info "Production environment: Preserving Redis data files"
    REDIS_CLEANUP_CMD=""
fi

# 启动Redis（在tmux中前台运行，不使用--daemonize）
tmux send-keys -t coze-fastapi:service.0 "cd '$PWD' && echo 'Redis Server' && echo '=============' && ${REDIS_CLEANUP_CMD}redis-server --port 6379 --daemonize no" Enter || {
    log_error "Unable to start Redis server"
    exit 1
}

# Wait for Redis to start
sleep 3

# Check if Redis started successfully
if ! redis-cli ping &>/dev/null; then
    log_error "Redis server startup failed"
    log_info "Checking Redis process..."
    pgrep -f "redis-server" || log_error "Redis process not found"
    exit 1
fi
log_success "Redis server started successfully"

# Start FastAPI service in panel 1
log_info "Starting FastAPI service..."

# Build environment variables
export APP_MODE="$MODE"
export ENABLE_AUTH="$ENABLE_AUTH"
export COZE_LOG_LEVEL="$LOG_LEVEL"
export PORT="$PORT"
export HOST="$HOST"

log_info "FastAPI configuration:"
log_info "  Mode: $MODE"
log_info "  Authentication: $([ "$ENABLE_AUTH" = "true" ] && echo "Enabled" || echo "Disabled")"
log_info "  Log level: $LOG_LEVEL"
log_info "  Host: $HOST"
log_info "  Port: $PORT"
log_info "  Startup command: uv run uvicorn app.main:app --host $HOST --port $PORT"

# 使用全局Python，通过uv运行
tmux send-keys -t coze-fastapi:service.1 "cd '$PWD' && echo 'Coze FastAPI Service' && echo '====================' && export APP_MODE='$MODE' && export ENABLE_AUTH='$ENABLE_AUTH' && export COZE_LOG_LEVEL='$LOG_LEVEL' && export PORT='$PORT' && export HOST='$HOST' && uv run uvicorn app.main:app --host $HOST --port $PORT" Enter || {
    log_error "Unable to start FastAPI service"
    exit 1
}
log_success "FastAPI service started successfully"

# Wait for FastAPI to start
sleep 3

# Set up log monitoring in panel 2
log_info "Setting up log monitoring..."
# 统一日志文件路径
LOG_FILE="logs/coze-fastapi.log"
# 确保日志目录存在
mkdir -p logs 2>/dev/null || true

# 如果日志文件不存在，创建一个空文件
if [ ! -f "$LOG_FILE" ]; then
    touch "$LOG_FILE"
    log_info "Created log file: $LOG_FILE"
fi

tmux send-keys -t coze-fastapi:service.2 "cd '$PWD' && echo 'Coze FastAPI Log Monitor' && echo '=========================' && echo 'Log file: $LOG_FILE' && tail -f $LOG_FILE" Enter || {
    log_error "Unable to set up log monitoring"
    exit 1
}
log_success "Log monitoring started"

# Verify service status
log_info "Verifying service status..."
log_info "Performing service health checks..."
sleep 3

# Check Redis connection
log_info "Checking Redis connection status..."
if command -v redis-cli &>/dev/null && redis-cli ping &>/dev/null; then
    log_success "Redis service connection normal (localhost:6379)"
else
    log_warning "Redis service connection abnormal, please confirm Redis is started"
fi

# Check FastAPI service
log_info "Checking FastAPI service connectivity..."
if curl -s http://${HOST}:${PORT}/coze/health &>/dev/null; then
    log_success "FastAPI service running normally (http://${HOST}:${PORT})"
else
    log_warning "FastAPI service may not be fully started, please check service window"
fi

# Check tmux session status
log_info "Checking service process status..."
if tmux list-sessions | grep -q "coze-fastapi"; then
    log_success "tmux session 'coze-fastapi' running normally"
    PANE_COUNT=$(tmux list-panes -t coze-fastapi:service | wc -l)
    log_info "Active panel count: $PANE_COUNT (Redis Server, FastAPI Server, Log Monitor)"
else
    log_error "tmux session 'coze-fastapi' not found"
fi

# Display success information
log_success "Service started successfully!"
echo
log_info "=== Service Access Information ==="
if [ "$MODE" = "local" ]; then
    log_info "FastAPI API address: http://127.0.0.1:${PORT}"
    log_info "Health check endpoint: http://127.0.0.1:${PORT}/coze/health"
    log_info "Authentication: Disabled, direct access to all endpoints"
else
    log_info "FastAPI API address: http://0.0.0.0:${PORT}"
    log_info "Health check endpoint: http://localhost:${PORT}/coze/health"
    log_info "Authentication: Enabled, valid JWT token required"
fi
log_info "Redis monitoring: redis://localhost:6379"
echo
log_info "=== Management Commands ==="
log_info "View service status: tmux attach -t coze-fastapi"
log_info "Stop all services: tmux kill-session -t coze-fastapi"
log_info "View Redis: tmux attach -t coze-fastapi:service -p 0"
log_info "View FastAPI: tmux attach -t coze-fastapi:service -p 1"
log_info "View logs: tmux attach -t coze-fastapi:service -p 2"
echo
log_info "tmux session information:"
echo "  Session name: coze-fastapi"
echo "  Panel layout:"
echo "    - Panel 0: Redis Server (port 6379)"
echo "    - Panel 1: FastAPI Web Server (port ${PORT})"
echo "    - Panel 2: Log Monitor (logs/coze-fastapi.log)"
echo
log_info "Common commands:"
echo "  List sessions: tmux list-sessions"
echo "  Attach session: tmux attach-session -t coze-fastapi"
echo "  Switch panels: Ctrl+b + arrow keys"
echo "  Exit session: Ctrl+b + d"
echo

# Check if running in interactive terminal
if [ -t 0 ] && [ -t 1 ]; then
    log_info "Connecting to tmux session..."
    tmux select-pane -t coze-fastapi:service.1
    tmux attach-session -t coze-fastapi
else
    log_info "Script execution completed, use 'tmux attach-session -t coze-fastapi' to connect to session"
fi

# Successful exit
trap - EXIT
exit 0

