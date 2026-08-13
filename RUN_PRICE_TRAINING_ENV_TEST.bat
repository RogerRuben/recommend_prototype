@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs

set "PYEXE=%CD%\runtime\venvs\price_training38\Scripts\python.exe"
if not exist "%PYEXE%" (
  echo [ERROR] Price training environment does not exist.
  echo Run CREATE_PRICE_TRAINING_ENV_PY38.bat first.
  pause
  exit /b 1
)

set "LOG=logs\price_training_environment_test.log"
"%PYEXE%" tests\price_training_environment_test.py > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
echo.
if "%RC%"=="0" (
  echo [PASS] Price training/export environment test completed.
) else (
  echo [FAIL] See %LOG%.
)
pause
exit /b %RC%
