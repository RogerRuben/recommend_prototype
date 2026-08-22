@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

if exist "runtime\python38\python.exe" goto start_services

if not exist "runtime\venvs\offline_py38\Scripts\python.exe" (
  echo [INFO] First use: preparing the packaged offline runtime.
  call INSTALL_OFFLINE_RUNTIME_WIN7.bat
  if errorlevel 1 exit /b 1
)

:start_services
call START_ALL_SERVICES_WIN7.bat
exit /b %ERRORLEVEL%
