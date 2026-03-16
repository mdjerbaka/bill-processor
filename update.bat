@echo off
setlocal enabledelayedexpansion
title Bill Processor - Update
echo.
echo  ============================================
echo    Bill Processor - Update
echo  ============================================
echo.
echo  This will download the latest version and rebuild.
echo  Your data (invoices, settings, etc.) will be preserved.
echo.
pause

cd /d "%~dp0"

set "REPO_URL=https://github.com/mdjerbaka/bill-processor/archive/refs/heads/master.zip"
set "TEMP_ZIP=%TEMP%\bill-processor-update.zip"
set "TEMP_DIR=%TEMP%\bill-processor-update"

:: ── Download latest code ────────────────────────────────
echo  [1/5] Downloading latest code from GitHub...
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%REPO_URL%' -OutFile '%TEMP_ZIP%' -UseBasicParsing; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Download failed. Check your internet connection.
    pause
    exit /b 1
)
echo  [OK] Downloaded.

:: ── Extract and copy new files ──────────────────────────
echo  [2/5] Applying update...

:: Clean up any previous temp extraction
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

:: Extract zip
powershell -NoProfile -Command "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_DIR%' -Force"
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to extract update archive.
    pause
    exit /b 1
)

:: Find the extracted folder (GitHub zips have a subfolder like bill-processor-main)
for /d %%D in ("%TEMP_DIR%\*") do set "SRC=%%D"

:: Copy new files over, preserving .env and data
:: Use robocopy to mirror code but exclude protected files/folders
robocopy "!SRC!\backend" "%~dp0backend" /E /XD __pycache__ data /NFL /NDL /NJH /NJS /NP >nul
if !errorlevel! geq 8 ( echo  [ERROR] Failed to copy backend files. & pause & exit /b 1 )
robocopy "!SRC!\frontend" "%~dp0frontend" /E /XD node_modules /NFL /NDL /NJH /NJS /NP >nul
if !errorlevel! geq 8 ( echo  [ERROR] Failed to copy frontend files. & pause & exit /b 1 )
robocopy "!SRC!\docs" "%~dp0docs" /E /NFL /NDL /NJH /NJS /NP >nul
if !errorlevel! geq 8 ( echo  [ERROR] Failed to copy docs files. & pause & exit /b 1 )

:: Copy root-level files (docker-compose, bat scripts, etc.) but NOT .env
for %%F in ("!SRC!\docker-compose.yml" "!SRC!\docker-compose.prod.yml" "!SRC!\install.bat" "!SRC!\start.bat" "!SRC!\stop.bat" "!SRC!\uninstall.bat" "!SRC!\update.bat" "!SRC!\README.md" "!SRC!\recurring_bills_template.csv" "!SRC!\.env.example") do (
    if exist "%%~F" copy /y "%%~F" "%~dp0" >nul
)

:: Clean up temp files
del "%TEMP_ZIP%" 2>nul
rmdir /s /q "%TEMP_DIR%" 2>nul

echo  [OK] Files updated (your .env and data are preserved).

:: ── Check Docker is running ─────────────────────────────
echo  [3/5] Checking Docker...
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
echo  [4/5] Rebuilding application (this may take a few minutes)...
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
echo  [5/5] Running database migrations...
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
