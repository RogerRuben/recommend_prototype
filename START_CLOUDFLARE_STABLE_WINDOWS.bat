@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYEXE="
if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (echo [ERROR] Python was not found.&pause&exit /b 1)
if not exist "deploy\cloudflare\cloudflared.exe" (
  where cloudflared >nul 2>&1
  if errorlevel 1 (
    echo cloudflared was not found. Downloading the official Windows binary...
    call INSTALL_CLOUDFLARED_WINDOWS.bat /silent
    if errorlevel 1 (echo [ERROR] cloudflared installation failed.&pause&exit /b 1)
  )
)
if not defined CLOUDFLARE_TUNNEL_TOKEN if not exist "deploy\cloudflare\tunnel_token.txt" (
  echo [ERROR] Stable tunnel token was not found.
  echo Set CLOUDFLARE_TUNNEL_TOKEN or create deploy\cloudflare\tunnel_token.txt.
  pause
  exit /b 1
)
set PYTHONUTF8=1
if not defined IPDEMO_AUTH_USERNAME set "IPDEMO_AUTH_USERNAME=ab123"
if not defined IPDEMO_AUTH_PASSWORD set "IPDEMO_AUTH_PASSWORD=ab123"
echo Starting the dashboard-managed Cloudflare Tunnel with login and read-only storage.
echo Login: %IPDEMO_AUTH_USERNAME% / %IPDEMO_AUTH_PASSWORD%
echo Configure the public hostname in the dashboard. Cloudflare Access remains optional defense-in-depth.
"%PYEXE%" tools\cloudflare_demo_launcher.py --mode token --port 17891 --port-span 0
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
