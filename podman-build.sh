#!/bin/bash
# Podman 镜像构建脚本
# 代理配置通过 --build-arg 传递给 Dockerfile

set -e

# 颜色定义
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

# 检查 Podman 是否运行
check_podman() {
    if ! podman info >/dev/null 2>&1; then
        log_error "Podman is not running, please start Podman first"
        exit 1
    fi
}

# 显示帮助信息
show_help() {
    echo "Podman Image Build Script for coze-fastapi"
    echo
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -h, --help          Show help information"
    echo "  --no-proxy          Build without proxy"
    echo "  --proxy-host HOST  Proxy host (default: host.containers.internal)"
    echo "  --proxy-port PORT  Proxy port (default: 7890)"
    echo "  --no-cache          Build without cache"
    echo "  -t, --tag TAG       Image tag (default: localhost/coze-fastapi:latest)"
    echo
    echo "Examples:"
    echo "  $0                      # Build with default proxy"
    echo "  $0 --no-proxy            # Build without proxy"
    echo "  $0 --no-cache            # Build without cache"
    echo "  $0 --proxy-port 8080    # Use custom proxy port"
    echo "  $0 --tag localhost/coze-fastapi:v1.0     # Specify image tag"
    echo
    echo "Note: Podman requires 'localhost/' prefix for local images"
}

# 默认配置
USE_PROXY=true

# 根据操作系统设置默认代理主机
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS: Podman 4.0+ 支持 host.containers.internal
    PROXY_HOST="${PROXY_HOST:-host.containers.internal}"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux: 使用主机 IP 或 host.containers.internal
    PROXY_HOST="${PROXY_HOST:-host.containers.internal}"
else
    PROXY_HOST="${PROXY_HOST:-host.containers.internal}"
fi

PROXY_PORT="${PROXY_PORT:-7890}"
NO_CACHE=""
IMAGE_TAG="localhost/coze-fastapi:latest"  # Podman 需要 localhost/ 前缀

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --no-proxy)
            USE_PROXY=false
            shift
            ;;
        --proxy-host)
            PROXY_HOST="$2"
            shift 2
            ;;
        --proxy-port)
            PROXY_PORT="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查 Podman
check_podman

# 构建代理参数
BUILD_ARGS=()
if [ "$USE_PROXY" = true ]; then
    HTTP_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
    HTTPS_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
    BUILD_ARGS+=("--build-arg" "HTTP_PROXY=${HTTP_PROXY}")
    BUILD_ARGS+=("--build-arg" "HTTPS_PROXY=${HTTPS_PROXY}")
    log_info "Using proxy: ${HTTP_PROXY}"
else
    log_info "Building without proxy"
fi

# 构建镜像
log_info "Building coze-fastapi image..."
log_info "Image tag: ${IMAGE_TAG}"
[ -n "$NO_CACHE" ] && log_info "Build mode: no cache"
echo

podman build \
    "${BUILD_ARGS[@]}" \
    ${NO_CACHE} \
    --tag "${IMAGE_TAG}" \
    --file Dockerfile \
    .

if [ $? -eq 0 ]; then
    echo
    log_success "Image built successfully: ${IMAGE_TAG}"
    echo
    echo "Run container with:"
    echo "  ./podman-run.sh"
else
    log_error "Image build failed"
    exit 1
fi

