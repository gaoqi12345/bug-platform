@echo off
title Bug Platform Launcher

echo.
echo ==========================================
echo   Bug Platform - Starting Services
echo ==========================================
echo.

echo [1/4] Checking Docker services...
docker ps --filter "name=bug-postgres" --filter "status=running" --format "{{.Names}}" 2>nul | findstr "bug-postgres" >nul
if errorlevel 1 (
    echo   Starting PostgreSQL...
    docker start bug-postgres >nul 2>&1
) else (
    echo   PostgreSQL  [OK]
)

docker ps --filter "name=bug-minio" --filter "status=running" --format "{{.Names}}" 2>nul | findstr "bug-minio" >nul
if errorlevel 1 (
    echo   Starting MinIO...
    docker start bug-minio >nul 2>&1
) else (
    echo   MinIO       [OK]
)

echo.
echo [2/4] Waiting for PostgreSQL...
set /a attempts=0
:wait_pg
set /a attempts+=1
docker exec bug-postgres pg_isready -U buguser -d bugplatform >nul 2>&1
if errorlevel 1 (
    if %attempts% geq 15 (
        echo   [ERROR] PostgreSQL not ready after 15s
        pause & exit /b 1
    )
    timeout /t 1 /nobreak >nul
    goto wait_pg
)
echo   PostgreSQL ready [OK]

echo.
echo [3/4] Starting Backend (port 8002)...

REM 检查 uv 是否安装
where uv >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] uv not found. Install uv first:
    echo     pip install uv
    echo   or visit: https://docs.astral.sh/uv/getting-started/installation/
    pause & exit /b 1
)

REM 检查 pyproject.toml 是否存在（依赖声明文件）
if not exist "%~dp0backend\pyproject.toml" (
    echo   [ERROR] pyproject.toml not found in backend/
    pause & exit /b 1
)

REM uv sync 自动创建 .venv 并安装依赖（如已是最新则跳过，很快）
echo   Syncing dependencies with uv...
cd /d "%~dp0backend"
uv sync >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] uv sync failed. Run manually: cd backend ^&^& uv sync
    pause & exit /b 1
)
echo   Dependencies ready [OK]

start "Backend :8002" cmd /k "cd /d %~dp0backend && uv run uvicorn app.main:app --reload --port 8002 --host 0.0.0.0"

echo   Waiting for backend...
set /a attempts=0
:wait_backend
set /a attempts+=1
curl -s http://localhost:8002/health >nul 2>&1
if errorlevel 1 (
    if %attempts% geq 20 (
        echo   [WARN] Backend timeout - check Backend window
        goto start_frontend
    )
    timeout /t 1 /nobreak >nul
    goto wait_backend
)
echo   Backend ready [OK]

:start_frontend
echo.
echo [4/4] Starting Frontend (port 8081)...
if not exist "%~dp0frontend\node_modules" (
    echo   [ERROR] node_modules not found. Run:
    echo     cd frontend
    echo     npm install
    pause & exit /b 1
)
start "Frontend :8081" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 4 /nobreak >nul

echo.
echo ==========================================
echo   All services started!
echo ==========================================
echo.
echo   Frontend    : http://localhost:8081
echo   Backend API : http://localhost:8002
echo   API Docs    : http://localhost:8002/docs
echo   MinIO       : http://localhost:9001
echo.
echo   Login : admin@bugplatform.com
echo   Pass  : Admin@123
echo.
echo ==========================================
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul
start http://localhost:8081

echo.
echo Press any key to close this window.
pause >nul
