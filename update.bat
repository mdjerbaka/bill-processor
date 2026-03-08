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

:: Check Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo  Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    :wait_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 goto wait_docker
)

echo.
echo  Rebuilding application (this may take a few minutes)...
echo.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Update failed. Please check the output above.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo    Update Complete!
echo  ============================================
echo.
echo  Bill Processor is running at http://localhost:3000
echo.
start http://localhost:3000
pause
