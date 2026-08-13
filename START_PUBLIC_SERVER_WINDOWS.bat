@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=logs\public_server.log"
set "PYEXE="
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (echo [ERROR] Python not found.&pause&exit /b 1)
if not defined IPDEMO_PORT set "IPDEMO_PORT=8080"
set PYTHONUTF8=1
echo ============================================================
echo V19.6 remote/public deployment
echo Listen: 0.0.0.0:%IPDEMO_PORT%
echo Put Nginx/IIS and authentication in front of this service.
echo ============================================================
%PYEXE% run_app.py --host 0.0.0.0 --port %IPDEMO_PORT% --port-span 0 --no-browser >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
pause
exit /b %RC%
