#!/bin/sh
# ============================================================
# Bug Platform — 容器启动入口
# 执行顺序：
#   1. 运行 Alembic 数据库迁移（PG 已由 Docker healthcheck 保证就绪）
#   2. 启动 Gunicorn + UvicornWorker
# ============================================================

set -e

# 标记当前运行在 Docker 容器内
# config.py 读到此变量后自动用 [docker.*] 节覆盖本地默认值
export RUNNING_IN_DOCKER=1

echo "=========================================="
echo "  Bug Platform Backend Starting..."
echo "=========================================="

# ── 1. 数据库迁移 ─────────────────────────────────────────────
# depends_on: service_healthy 已确保 PostgreSQL 就绪，无需再探活
echo "[1/2] Running database migrations..."
uv run alembic upgrade head
echo "  Migrations applied [OK]"

# ── 2. 启动服务 ───────────────────────────────────────────────
# Gunicorn 负责进程管理（优雅重启/worker 崩溃恢复/信号处理）
# UvicornWorker 负责 ASGI 协议处理
echo "[2/2] Starting server..."
echo "=========================================="
exec uv run gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --bind 0.0.0.0:8001 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile -
