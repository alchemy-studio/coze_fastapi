#!/bin/bash
# pre_check.sh - 检查 podman 和 podman-compose 版本
# 在运行 podman-run.sh 之前调用，确保环境满足要求

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 最低版本要求
MIN_PODMAN_VERSION="3.0.0"
MIN_COMPOSE_VERSION="1.0.0"

# 版本比较函数
# 返回 0 表示 $1 >= $2
version_ge() {
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# 检查 podman
check_podman() {
    log_info "检查 podman..."
    
    if ! command -v podman &> /dev/null; then
        log_error "podman 未安装"
        echo ""
        read -p "是否需要安装 podman? (y/n): " answer
        if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
            echo ""
            echo "请根据您的系统执行以下命令安装："
            echo "  CentOS/RHEL: sudo dnf install -y podman"
            echo "  Ubuntu/Debian: sudo apt install -y podman"
            echo "  macOS: brew install podman"
            echo ""
        fi
        return 1
    fi
    
    # 获取版本号
    PODMAN_VERSION=$(podman --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "0.0.0")
    
    if [ -z "$PODMAN_VERSION" ] || [ "$PODMAN_VERSION" = "0.0.0" ]; then
        log_warning "无法获取 podman 版本号"
        PODMAN_VERSION="unknown"
    fi
    
    log_success "podman 已安装 (版本: $PODMAN_VERSION)"
    
    # 检查版本是否过旧
    if [ "$PODMAN_VERSION" != "unknown" ] && ! version_ge "$PODMAN_VERSION" "$MIN_PODMAN_VERSION"; then
        log_warning "podman 版本 ($PODMAN_VERSION) 低于推荐版本 ($MIN_PODMAN_VERSION)"
        read -p "是否继续? (y/n): " answer
        if [ "$answer" != "y" ] && [ "$answer" != "Y" ]; then
            return 1
        fi
    fi
    
    return 0
}

# 检查 podman-compose
check_podman_compose() {
    log_info "检查 podman-compose..."
    
    if ! command -v podman-compose &> /dev/null; then
        log_error "podman-compose 未安装"
        echo ""
        read -p "是否需要安装 podman-compose? (y/n): " answer
        if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
            echo ""
            echo "请执行以下命令安装："
            echo "  pip install podman-compose"
            echo "  或"
            echo "  pip3 install podman-compose"
            echo ""
        fi
        return 1
    fi
    
    # 获取版本号
    COMPOSE_VERSION=$(podman-compose --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "0.0.0")
    
    if [ -z "$COMPOSE_VERSION" ] || [ "$COMPOSE_VERSION" = "0.0.0" ]; then
        # 尝试其他方式获取版本
        COMPOSE_VERSION=$(podman-compose version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")
    fi
    
    log_success "podman-compose 已安装 (版本: $COMPOSE_VERSION)"
    
    # 检查版本是否过旧（警告但不阻止）
    if [ "$COMPOSE_VERSION" != "unknown" ] && ! version_ge "$COMPOSE_VERSION" "$MIN_COMPOSE_VERSION"; then
        log_warning "podman-compose 版本 ($COMPOSE_VERSION) 较旧，部分功能可能不可用"
        log_info "建议升级: pip install --upgrade podman-compose"
    fi
    
    return 0
}

# 检查 podman 是否正在运行（macOS）
check_podman_running() {
    # 只在 macOS 上检查
    if [[ "$OSTYPE" == "darwin"* ]]; then
        log_info "检查 Podman 服务状态..."
        if ! podman info &> /dev/null; then
            log_error "Podman 服务未运行"
            echo ""
            echo "请先启动 Podman Desktop 或执行: podman machine start"
            echo ""
            return 1
        fi
        log_success "Podman 服务正在运行"
    fi
    return 0
}

# 主函数
main() {
    echo ""
    echo "========================================="
    echo "  Podman 环境检查"
    echo "========================================="
    echo ""
    
    local has_error=0
    
    # 检查 podman
    if ! check_podman; then
        has_error=1
    fi
    
    # 检查 podman-compose
    if ! check_podman_compose; then
        has_error=1
    fi
    
    # 检查 podman 服务是否运行
    if [ $has_error -eq 0 ]; then
        if ! check_podman_running; then
            has_error=1
        fi
    fi
    
    echo ""
    
    if [ $has_error -eq 1 ]; then
        log_error "环境检查未通过，请先安装/配置必要的软件"
        return 1
    fi
    
    log_success "环境检查通过"
    echo ""
    return 0
}

# 如果直接运行此脚本（而非被 source）
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
