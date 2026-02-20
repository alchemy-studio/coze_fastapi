#!/bin/bash
# Podman 容器管理脚本
# 功能：启动、停止、进入容器
# 注意：使用 podman-compose_dev.yml 中的 volume 配置实现代码实时同步
# 注意：容器内端口固定为6000，主机端口可通过参数或环境变量配置

set -euo pipefail

# 默认端口配置
DEFAULT_PORT=6000
CONTAINER_PORT=6000  # 容器内部端口固定为 6000
HOST_PORT="${DEFAULT_PORT}"  # 主机端口，可通过参数或环境变量设置

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

# 运行环境检查
run_pre_check() {
    if [ -f "./pre_check.sh" ]; then
        log_info "Running environment check..."
        if ! ./pre_check.sh; then
            log_error "Environment check failed"
            exit 1
        fi
    fi
}

# 检查 Podman 是否运行
check_podman() {
    if ! podman info >/dev/null 2>&1; then
        log_error "Podman is not running, please start Podman first"
        exit 1
    fi
}

# 检查镜像是否存在
check_image() {
    if ! podman image exists localhost/coze-fastapi:latest 2>/dev/null; then
        log_warning "Image localhost/coze-fastapi:latest not found"
        log_info "Building image..."
        if [ -f "./podman-build.sh" ]; then
            ./podman-build.sh
        else
            log_error "Build script not found: ./podman-build.sh"
            exit 1
        fi
    fi
}

# 停止容器
stop_container() {
    if podman ps -q --filter name=coze-fastapi | grep -q .; then
        log_info "Stopping container..."
        podman-compose -f podman-compose_dev.yml down
        log_success "Container stopped"
    else
        log_info "Container is not running"
    fi
}

# 启动容器
start_container() {
    log_info "Starting container on port ${HOST_PORT}..."
    
    # 使用环境变量传递端口配置给 podman-compose
    HOST_PORT="${HOST_PORT}" podman-compose -f podman-compose_dev.yml up -d --force-recreate
    if [ $? -eq 0 ]; then
        log_success "Container started successfully"
        log_info "FastAPI will be available at: http://localhost:${HOST_PORT}"
    else
        log_error "Container start failed"
        exit 1
    fi
}

# 进入容器
enter_container() {
    log_info "Entering container..."
    # 使用 podman exec 替代 podman-compose exec（兼容旧版本 podman-compose）
    podman exec -it coze-fastapi /bin/bash
}

# 等待容器就绪
wait_for_container() {
    log_info "Waiting for container to be ready..."
    sleep 2
    if podman ps -q --filter name=coze-fastapi | grep -q .; then
        log_success "Container is running"
    else
        log_error "Container failed to start"
        exit 1
    fi
}

# 解析端口参数
parse_port_argument() {
    local arg="$1"
    # 检查是否是数字（端口号）
    if [[ "$arg" =~ ^[0-9]+$ ]] && [ "$arg" -ge 1024 ] && [ "$arg" -le 65535 ]; then
        echo "$arg"
        return 0
    fi
    return 1
}

# 显示帮助信息
show_help() {
    echo "Podman Container Management Script for coze-fastapi"
    echo
    echo "Usage: $0 [command] [port]"
    echo
    echo "Commands:"
    echo "  start [PORT]   Start container (default port: 6000)"
    echo "  stop           Stop container"
    echo "  enter          Enter running container"
    echo "  restart [PORT] Restart container"
    echo "  build [PORT]   Force rebuild image before starting"
    echo
    echo "Options:"
    echo "  -h, --help     Show help information"
    echo
    echo "Port:"
    echo "  Optional port number (1024-65535) to map container port 6000 to host"
    echo "  Default: 6000"
    echo "  Can also be set via HOST_PORT environment variable"
    echo
    echo "Examples:"
    echo "  $0              # Start on default port 6000"
    echo "  $0 6001        # Start on port 6001"
    echo "  $0 start 6001  # Start on port 6001"
    echo "  $0 stop        # Stop container"
    echo "  $0 enter       # Enter running container"
    echo "  $0 restart 6001 # Restart on port 6001"
    echo "  HOST_PORT=6001 $0 start  # Use environment variable"
}

# 主函数
main() {
    local command=""
    local args=("$@")
    
    # 如果设置了环境变量，使用环境变量
    if [ -n "${HOST_PORT:-}" ]; then
        HOST_PORT="${HOST_PORT}"
    else
        HOST_PORT="${DEFAULT_PORT}"
    fi
    
    # 解析参数
    local i=0
    while [ $i -lt ${#args[@]} ]; do
        local arg="${args[$i]}"
        
        case "$arg" in
            -h|--help)
                show_help
                exit 0
                ;;
            start|stop|enter|restart|build)
                command="$arg"
                i=$((i + 1))
                # 检查下一个参数是否是端口号
                if [ $i -lt ${#args[@]} ]; then
                    local next_arg="${args[$i]}"
                    if parse_port_argument "$next_arg" >/dev/null 2>&1; then
                        HOST_PORT=$(parse_port_argument "$next_arg")
                        i=$((i + 1))
                    fi
                fi
                break
                ;;
            *)
                # 如果第一个参数是数字，可能是端口号
                if [ -z "$command" ] && parse_port_argument "$arg" >/dev/null 2>&1; then
                    HOST_PORT=$(parse_port_argument "$arg")
                    command="start"  # 默认命令
                    i=$((i + 1))
                elif [ -z "$command" ]; then
                    command="$arg"
                    i=$((i + 1))
                else
                    log_error "Unknown argument: $arg"
                    show_help
                    exit 1
                fi
                ;;
        esac
    done
    
    # 如果没有指定命令，默认为 start
    command="${command:-start}"
    
    # 验证端口范围
    if [ "$HOST_PORT" -lt 1024 ] || [ "$HOST_PORT" -gt 65535 ]; then
        log_error "Invalid port: ${HOST_PORT}. Port must be between 1024 and 65535"
        exit 1
    fi
    
    case "$command" in
        start)
            # 运行环境检查
            run_pre_check
            
            # 检查 Podman
            check_podman
            
            # 检查镜像
            check_image
            
            # 停止现有容器
            if podman ps -q --filter name=coze-fastapi | grep -q .; then
                stop_container
            fi
            
            # 启动容器
            start_container
            
            # 等待容器就绪
            wait_for_container
            
            # 进入容器
            enter_container
            ;;
        stop)
            check_podman
            stop_container
            ;;
        enter)
            check_podman
            if ! podman ps -q --filter name=coze-fastapi | grep -q .; then
                log_error "Container is not running, please start it first"
                exit 1
            fi
            enter_container
            ;;
        restart)
            run_pre_check
            check_podman
            stop_container
            sleep 2
            check_image
            start_container
            wait_for_container
            log_success "Container restarted"
            log_info "Use './podman-run.sh enter' to enter container"
            ;;
        build)
            run_pre_check
            check_podman
            log_info "Force rebuilding image..."
            if [ -f "./podman-build.sh" ]; then
                ./podman-build.sh
            else
                log_error "Build script not found: ./podman-build.sh"
                exit 1
            fi
            if [ $? -ne 0 ]; then
                log_error "Image build failed"
                exit 1
            fi
            log_success "Image built successfully"
            
            # 停止现有容器
            if podman ps -q --filter name=coze-fastapi | grep -q .; then
                stop_container
            fi
            
            # 启动容器
            start_container
            wait_for_container
            enter_container
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"

