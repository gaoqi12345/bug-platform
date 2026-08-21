FROM docker.m.daocloud.io/library/python:3.11-slim

# 从官方镜像复制 uv 二进制（构建阶段用，运行时也可用）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖声明文件，利用 Docker 层缓存
# 只要 pyproject.toml / uv.lock 没变，依赖层就不会重新构建
COPY pyproject.toml uv.lock ./

# 安装生产依赖（--frozen 严格按锁文件，--no-dev 排除 pytest 等测试依赖）
RUN uv sync --frozen --no-dev

# 复制应用代码
COPY . .

# 复制并授权启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 健康检查
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001

ENTRYPOINT ["/entrypoint.sh"]
