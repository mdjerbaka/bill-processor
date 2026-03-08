@echo off
title Bill Processor
echo.
echo  Starting Bill Processor...
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo  Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo  Waiting for Docker to start...
    :wait_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 goto wait_docker
    echo  Docker is ready.
)

:: Start containers
cd /d "%~dp0"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to start. Try running install.bat first.
    pause
    exit /b 1
)

echo.
echo  Bill Processor is running at http://localhost:3000
echo  Opening in your browser...
echo.
timeout /t 2 /nobreak >nul
start http://localhost:3000
