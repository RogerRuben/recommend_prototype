@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "SILENT=0"
if /I "%~1"=="/silent" set "SILENT=1"
if not exist "deploy\cloudflare" mkdir "deploy\cloudflare"
set "TARGET=%CD%\deploy\cloudflare\cloudflared.exe"
set "URL=https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
echo ============================================================
echo Download Cloudflare cloudflared from the official release URL
echo Target: %TARGET%
echo ============================================================
where powershell >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PowerShell was not found.
  echo Download cloudflared-windows-amd64.exe manually from Cloudflare,
  echo rename it to cloudflared.exe, and place it in deploy\cloudflare.
  if "%SILENT%"=="0" pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '%TARGET%'"
if errorlevel 1 (
  echo [ERROR] Download failed. Check network/TLS settings or download manually.
  if "%SILENT%"=="0" pause
  exit /b 1
)
"%TARGET%" version
if errorlevel 1 (
  echo [ERROR] cloudflared.exe could not run on this Windows version.
  echo Current cloudflared is intended for supported modern Windows systems.
  del /q "%TARGET%" >nul 2>&1
  if "%SILENT%"=="0" pause
  exit /b 1
)
echo [OK] cloudflared is ready.
if "%SILENT%"=="0" pause
exit /b 0
