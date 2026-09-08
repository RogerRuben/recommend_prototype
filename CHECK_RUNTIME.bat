@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "runtime\python38\python.exe" (
  echo [ERROR] Missing Python 3.8 / sklearn 0.24.1 runtime.
  pause
  exit /b 1
)
"runtime\python38\python.exe" tools\verify_field_runtime.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
