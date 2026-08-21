@echo off
title Bug Platform - Stop

echo.
echo Stopping Bug Platform services...

set "FAILED=0"
set "FOUND=0"

rem ===== Backend on 8002 =====
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002" ^| findstr "LISTENING" 2^>nul') do (
    if not defined _PID_%%a (
        set "_PID_%%a=1"
        set "FOUND=1"
        echo   Killing backend  PID: %%a
        taskkill /PID %%a /F >nul 2>&1
        if errorlevel 1 (
            echo     [WARN] Failed to kill PID %%a:
            taskkill /PID %%a /F
            set "FAILED=1"
        ) else (
            echo     [OK]   Killed PID %%a
        )
    )
)

rem ===== Frontend on 8081 =====
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081" ^| findstr "LISTENING" 2^>nul') do (
    if not defined _PID_%%a (
        set "_PID_%%a=1"
        set "FOUND=1"
        echo   Killing frontend PID: %%a
        taskkill /PID %%a /F >nul 2>&1
        if errorlevel 1 (
            echo     [WARN] Failed to kill PID %%a:
            taskkill /PID %%a /F
            set "FAILED=1"
        ) else (
            echo     [OK]   Killed PID %%a
        )
    )
)

echo.
if "%FOUND%"=="0" (
    echo   No process was listening on 8002/8081 - nothing to stop
) else if "%FAILED%"=="1" (
    echo   [WARN] Some processes could not be stopped.
    echo   They are likely running with administrator privileges.
    echo.
    echo   Options:
    echo     1. Close the terminal that started them, then re-run.
    echo     2. Right-click stop.bat -^> "Run as administrator".
    echo     3. Kill them manually:
    echo          netstat -ano ^| findstr ":8002 :8081"
    echo          taskkill /PID ^<pid^> /F
) else (
    echo   Backend  (8002) stopped
    echo   Frontend (8081) stopped
)

echo   Docker containers kept running
echo.
echo   To stop Docker too:
echo     docker stop bug-postgres bug-minio
echo.
pause