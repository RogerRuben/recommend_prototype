@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "RC=0"
if exist "runtime\venvs\model_runtime38\Scripts\python.exe" (
  echo [INFO] Verifying unified model runtime...
  "runtime\venvs\model_runtime38\Scripts\python.exe" tools\verify_model_environment.py --profile runtime --smoke-current-models
  if errorlevel 1 set "RC=1"
) else (
  echo [WARN] runtime\venvs\model_runtime38 does not exist.
  set "RC=1"
)

if exist "runtime\venvs\price_training38\Scripts\python.exe" (
  echo.
  echo [INFO] Verifying price training environment...
  "runtime\venvs\price_training38\Scripts\python.exe" tools\verify_model_environment.py --profile training
  if errorlevel 1 set "RC=1"
) else (
  echo [WARN] runtime\venvs\price_training38 does not exist.
)

echo.
if "%RC%"=="0" (
  echo [PASS] Available model environments passed verification.
) else (
  echo [FAIL] At least one required environment is missing or invalid.
)
pause
exit /b %RC%
