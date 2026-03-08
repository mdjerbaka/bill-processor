@echo off
setlocal enabledelayedexpansion

:: ── Always run from the folder where install.bat lives ──
cd /d "%~dp0"

title Bill Processor - Installer
color 0A
echo.
echo  ============================================
echo    Bill Processor - One-Click Installer
echo  ============================================
echo.

:: ── Check for Admin rights ──────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] This installer needs to run as Administrator.
    echo      Right-click install.bat and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

:: ── Check if Docker is installed ────────────────────────
echo  [1/6] Checking for Docker Desktop...
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Docker Desktop is not installed.
    echo  Opening the Docker Desktop download page...
    echo.
    echo  Please:
    echo    1. Download and install Docker Desktop
    echo    2. Restart your computer if prompted
    echo    3. Run this installer again
    echo.
    start https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo  [OK] Docker found.

:: ── Check if Docker daemon is running ───────────────────
echo  [2/6] Checking Docker is running...
docker info >nul 2>&1
if %errorlevel% neq 0 goto start_docker
goto docker_ready

:start_docker
echo.
echo  Docker Desktop is installed but not running.
echo  Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo  Waiting for Docker to start (this may take a minute)...

:wait_docker
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if %errorlevel% neq 0 goto wait_docker

:docker_ready
echo  [OK] Docker is running.

:: ── Generate .env if it doesn't exist ───────────────────
echo  [3/6] Configuring environment...
if exist ".env" (
    echo  [OK] .env already exists, keeping current config.
) else (
    copy .env.example .env >nul

    :: Generate SECRET_KEY (64 hex chars using PowerShell)
    for /f "delims=" %%k in ('powershell -NoProfile -Command "[System.Guid]::NewGuid().ToString('N') + [System.Guid]::NewGuid().ToString('N')"') do set "NEW_SECRET=%%k"

    :: Generate ENCRYPTION_KEY (Fernet-compatible base64 key using PowerShell)
    for /f "delims=" %%k in ('powershell -NoProfile -Command "$bytes = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes); [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_')"') do set "NEW_FERNET=%%k="

    :: Replace placeholders in .env
    powershell -NoProfile -Command "(Get-Content .env) -replace 'SECRET_KEY=REPLACE_ME', 'SECRET_KEY=!NEW_SECRET!' | Set-Content .env"
    powershell -NoProfile -Command "(Get-Content .env) -replace 'ENCRYPTION_KEY=REPLACE_ME', 'ENCRYPTION_KEY=!NEW_FERNET!' | Set-Content .env"

    echo  [OK] Generated .env with secure keys.
)

:: ── Build and start containers ──────────────────────────
echo  [4/6] Building application (first run takes 3-5 minutes)...
echo.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Docker build failed. Please check the output above.
    pause
    exit /b 1
)

:: ── Wait for health check ───────────────────────────────
echo.
echo  [5/6] Waiting for application to start...
set retries=0
:health_loop
timeout /t 3 /nobreak >nul
set /a retries+=1

:: Use PowerShell to make HTTP request since curl may not be available
for /f "delims=" %%s in ('powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/health' -UseBasicParsing -TimeoutSec 3; $r.StatusCode } catch { 0 }"') do set "STATUS=%%s"

if "%STATUS%"=="200" goto health_ok
if %retries% geq 20 (
    echo  [WARN] Health check timed out, but the app may still be starting.
    echo         Try opening http://localhost:3000 in your browser.
    goto create_shortcut
)
echo  Waiting... (%retries%/20)
goto health_loop

:health_ok
echo  [OK] Application is healthy!

:: ── Create desktop shortcut ─────────────────────────────
:create_shortcut
echo  [6/6] Creating desktop shortcut...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([IO.Path]::Combine($ws.SpecialFolders('Desktop'), 'Bill Processor.lnk')); $s.TargetPath = '%~dp0start.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,14'; $s.Description = 'Open Bill Processor'; $s.Save()"
echo  [OK] Shortcut created on Desktop.

:: ── Configure Docker Desktop to start on login ──────────
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Docker Desktop" /t REG_SZ /d "\"C:\Program Files\Docker\Docker\Docker Desktop.exe\"" /f >nul 2>&1

:: ── Done ────────────────────────────────────────────────
echo.
echo  ============================================
echo    Installation Complete!
echo  ============================================
echo.
echo  Opening Bill Processor in your browser...
echo  URL: http://localhost:3000
echo.
echo  Follow the Setup Wizard to:
echo    1. Create your admin account
echo    2. Configure your email connection
echo    3. You're done! (QuickBooks + OCR in Settings later)
echo.
echo  A "Bill Processor" shortcut has been added to your Desktop.
echo  The app starts automatically when your computer turns on.
echo.
start http://localhost:3000
pause
