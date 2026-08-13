@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYEXE="
if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (
  echo [ERROR] Python was not found.
  pause
  exit /b 1
)
if not exist "deploy\cloudflare\cloudflared.exe" (
  where cloudflared >nul 2>&1
  if errorlevel 1 (
    echo cloudflared was not found. Downloading the official Windows binary...
    call INSTALL_CLOUDFLARED_WINDOWS.bat /silent
    if errorlevel 1 (
      echo [ERROR] cloudflared installation failed.
      pause
      exit /b 1
    )
  )
)
set PYTHONUTF8=1
if not defined IPDEMO_AUTH_USERNAME set "IPDEMO_AUTH_USERNAME=ab123"
if not defined IPDEMO_AUTH_PASSWORD set "IPDEMO_AUTH_PASSWORD=ab123"
echo ============================================================
echo V19.6 Cloudflare Login Demo

echo - Random trycloudflare.com URL

echo - Login required: %IPDEMO_AUTH_USERNAME% / %IPDEMO_AUTH_PASSWORD%

echo - All pages visible after login; server-side writes are disabled

echo - Press Ctrl+C to stop both processes

echo ============================================================
"%PYEXE%" tools\cloudflare_demo_launcher.py --mode quick --open-browser
set "RC=%ERRORLEVEL%"
echo.
echo Cloudflare demo stopped with code %RC%.
echo Logs: logs\cloudflare_app.log and logs\cloudflare_tunnel.log
pause
exit /b %RC%
