@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "runtime\python38\python.exe" (
  echo [ERROR] Missing field Python 3.8 runtime.
  pause
  exit /b 1
)
if not exist "runtime\price_python38\python.exe" (
  echo [ERROR] Missing isolated price Python 3.8 runtime.
  pause
  exit /b 1
)
"runtime\python38\python.exe" tools\verify_dual_runtime.py --price-python "runtime\price_python38\python.exe"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
