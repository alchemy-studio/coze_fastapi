# Multi-stage build for coze-fastapi
# 使用 uv 管理 Python 依赖

# ============================================================================
# Stage 1: Builder - 安装构建工具和编译依赖
# ============================================================================
FROM centos:8 AS builder

# 设置代理（构建时可通过 --build-arg 传递）
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

# 更新 dnf mirror list
RUN cd /etc/yum.repos.d/ \
  && sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-* \
  && sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*

# 安装 EPEL
RUN dnf -y install dnf-plugins-core && \
    dnf -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm && \
    dnf install -y epel-release dnf-utils

# 安装基础工具
RUN dnf install -y \
        python3 python3-pip \
        wget curl git \
        ca-certificates && \
    update-ca-trust || true

# 安装 uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# 使用 uv 安装 Python 3.10（与 ai-api 保持一致）
RUN uv python list || true && \
    (uv python install 3.10.1 || \
     uv python install 3.10 || \
     uv python install 3.10.11 || \
     (python3 -m pip install --upgrade pip && \
      python3 -m pip install uv[python] && \
      uv python install 3.10.1)) || \
    echo "警告: Python 安装可能失败，请检查"

# 固定 Python 版本（使用实际安装的版本）
RUN uv python pin 3.10 || true

# 配置 Python 环境变量（查找实际安装的 Python 3.10）
RUN PYTHON_FULL_PATH=$(uv python find 3.10 2>/dev/null || echo "") && \
    if [ -n "$PYTHON_FULL_PATH" ]; then \
        PYTHON_PATH=$(dirname "$PYTHON_FULL_PATH" 2>/dev/null || echo "") && \
        if [ -n "$PYTHON_PATH" ]; then \
            echo "export PATH=\"$PYTHON_PATH:\${PATH}\"" >> /root/.bashrc && \
            echo "export UV_PYTHON=3.10" >> /root/.bashrc && \
            echo "$PYTHON_FULL_PATH" > /tmp/uv_python_path && \
            echo "Python path configured: $PYTHON_PATH"; \
        else \
            echo "⚠️  警告: 无法获取 Python 目录路径"; \
        fi; \
    else \
        echo "⚠️  警告: 未找到 Python 3.10 路径"; \
    fi

# 验证 Python 环境（使用 uv 安装的 Python）
RUN export PATH="/root/.local/bin:${PATH}" && \
    PYTHON_EXE=$(uv python find 3.10 2>/dev/null || echo "") && \
    if [ -n "$PYTHON_EXE" ]; then \
        echo "=== Python 环境验证 ===" && \
        $PYTHON_EXE --version && \
        $PYTHON_EXE -c 'import sys; print("Python executable:", sys.executable)' && \
        $PYTHON_EXE -c 'import site; print("Site-packages:", site.getsitepackages()[0])' && \
        echo "✅ Python 环境配置完成"; \
    else \
        echo "⚠️  警告: 未找到 Python 3.10，跳过验证"; \
    fi

# 复制项目文件
WORKDIR /coze-fastapi
COPY pyproject.toml README.md ./

# 使用 uv 安装依赖（先复制代码以便构建）
COPY app/ ./app/

# 使用 uv 安装依赖（使用 Python 3.10）
RUN uv sync

# ============================================================================
# Stage 2: Runtime - 只包含运行时依赖
# ============================================================================
FROM centos:8 AS runtime

# 设置代理（运行时通常不需要，但保留环境变量）
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

# 更新 dnf mirror list
RUN cd /etc/yum.repos.d/ \
  && sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-* \
  && sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*

# 安装 EPEL
RUN dnf -y install dnf-plugins-core && \
    dnf -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm && \
    dnf install -y epel-release dnf-utils

# 安装运行时需要的系统库和工具
RUN dnf install -y \
        python3 \
        ca-certificates \
        tmux \
        wget \
        curl \
        git \
        vim \
        htop \
        redis \
        lsof \
        procps-ng \
        util-linux \
        && \
    update-ca-trust || true

# 从 builder 复制 uv 和 Python 环境
COPY --from=builder /root/.local/bin/uv /root/.local/bin/
COPY --from=builder /root/.local/share/uv /root/.local/share/uv

# 从 builder 复制项目代码、依赖和虚拟环境
COPY --from=builder /coze-fastapi /coze-fastapi

# 设置工作目录
WORKDIR /coze-fastapi

# 设置基础 PATH（包含 uv）
ENV PATH="/root/.local/bin:${PATH}"

# 设置 SSL 证书环境变量
ENV SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt
ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt

# 暴露端口（容器内固定为6000）
EXPOSE 6000

# 设置环境变量
ENV PORT=6000
ENV HOST=0.0.0.0

# 启动命令
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "6000"]

