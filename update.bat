@echo off
title Bill Processor - Update
echo.
echo  ============================================
echo    Bill Processor - Update
echo  ============================================
echo.
echo  This will update the application to the latest version.
echo  Your data (invoices, settings, etc.) will be preserved.
echo.
pause

cd /d "%~dp0"

:: ── Check Git is available ──────────────────────────────
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Git is not installed or not in PATH.
    echo  Please install Git from https://git-scm.com/downloads
    pause
    exit /b 1
)

:: ── Pull latest code ────────────────────────────────────
echo  [1/4] Pulling latest code from repository...
git pull origin master
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Git pull failed. Check your internet connection
    echo         and that there are no local file conflicts.
    pause
    exit /b 1
)
echo  [OK] Code updated.

:: ── Check Docker is running ─────────────────────────────
echo  [2/4] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo  Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    :wait_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 goto wait_docker
)
echo  [OK] Docker is running.

:: ── Rebuild and restart containers ──────────────────────
echo  [3/4] Rebuilding application (this may take a few minutes)...
echo.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Docker build failed. Please check the output above.
    pause
    exit /b 1
)
echo  [OK] Containers rebuilt.

:: ── Run database migrations ─────────────────────────────
echo  [4/4] Running database migrations...
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head
if %errorlevel% neq 0 (
    echo.
    echo  [WARN] Database migration had issues. The app may still work.
    echo         Check the output above for details.
)
echo  [OK] Database up to date.

echo.
echo  ============================================
echo    Update Complete!
echo  ============================================
echo.
echo  Bill Processor is running at http://localhost:3000
echo.
start http://localhost:3000
pause
