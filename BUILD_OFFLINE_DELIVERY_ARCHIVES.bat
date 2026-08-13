@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "OUTPUT_DIR=%~1"
if not defined OUTPUT_DIR set "OUTPUT_DIR=%USERPROFILE%\Desktop\IndustrialProtocolDemo_V19_6_Offline_Delivery"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_offline_delivery_archives.ps1" -ProjectRoot "%CD%" -OutputDir "%OUTPUT_DIR%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo [ERROR] Delivery archive build failed.
  pause
  exit /b %RC%
)

echo.
echo [OK] Delivery archives were created under:
echo      %OUTPUT_DIR%
pause
exit /b 0
