@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo [INFO] Price and effectiveness services now share the verified model_runtime38 environment.
call "%~dp0CREATE_MODEL_RUNTIME_ENV_WIN7.bat"
exit /b %ERRORLEVEL%
