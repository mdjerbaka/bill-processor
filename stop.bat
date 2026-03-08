@echo off
title Bill Processor - Stop
echo.
echo  Stopping Bill Processor...
echo.

cd /d "%~dp0"
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

echo.
echo  Bill Processor has been stopped.
echo  Your data is preserved. Run start.bat to restart.
echo.
pause
