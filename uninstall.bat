@echo off
title Bill Processor - Uninstall
echo.
echo  ============================================
echo    Bill Processor - Uninstall
echo  ============================================
echo.
echo  This will remove all Bill Processor data including:
echo    - Docker containers and images
echo    - Database (all invoices, settings, accounts)
echo    - Configuration (.env file)
echo.
echo  After uninstalling, run install.bat to start fresh.
echo.
set /p confirm="  Are you sure? Type YES to confirm: "
if /i not "%confirm%"=="YES" (
    echo  Cancelled.
    pause
    exit /b 0
)

cd /d "%~dp0"

echo.
echo  Stopping containers...
docker compose down -v 2>nul

echo  Removing images...
docker rmi bill-processor-api bill-processor-worker bill-processor-frontend 2>nul

echo  Removing configuration...
if exist ".env" del ".env"

echo.
echo  ============================================
echo    Uninstall Complete
echo  ============================================
echo.
echo  To reinstall, run install.bat
echo.
pause
