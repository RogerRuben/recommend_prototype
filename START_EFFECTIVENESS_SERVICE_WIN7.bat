@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "logs" mkdir "logs"
set "LOGFILE=%CD%\logs\effectiveness_service.log"

set "PYEXE="
if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"

if not defined PYEXE (
  echo [ERROR] Python was not found.
  echo [ERROR] Python was not found.>"%LOGFILE%"
  pause
  exit /b 1
)

set "PYTHONUTF8=1"
set "MODE="
set "ARGS="

if defined EFFECT_SOURCE_ROOT (
  if not defined EFFECT_WORKBOOK (
    echo [ERROR] EFFECT_SOURCE_ROOT is set, but EFFECT_WORKBOOK is empty.
    echo [ERROR] EFFECT_SOURCE_ROOT is set, but EFFECT_WORKBOOK is empty.>"%LOGFILE%"
    pause
    exit /b 1
  )
  set "MODE=original source runtime"
  set "ARGS=--source-root "%EFFECT_SOURCE_ROOT%" --workbook "%EFFECT_WORKBOOK%""
  if defined EFFECT_STATE set "ARGS=%ARGS% --state "%EFFECT_STATE%""
  goto launch_service
)

if exist "services\effectiveness_service\model\current\effectiveness_runtime_manifest.json" (
  set "MODE=packaged runtime - frozen V11 or legacy Workbook+State"
  set "ARGS=--package "services\effectiveness_service\model\current\effectiveness_runtime_manifest.json""
  goto launch_service
)

if not exist "models\effectiveness_bundle.json" (
  echo [ERROR] Neither a frozen/legacy runtime package nor models\effectiveness_bundle.json was found.
  echo [ERROR] No usable effectiveness model was found.>"%LOGFILE%"
  pause
  exit /b 1
)

set "MODE=portable snapshot"
set "ARGS=--snapshot "models\effectiveness_bundle.json""

:launch_service
> "%LOGFILE%" echo Effectiveness service startup log
>>"%LOGFILE%" echo Mode: %MODE%
>>"%LOGFILE%" echo Python: %PYEXE%
>>"%LOGFILE%" echo Started: %DATE% %TIME%

echo [INFO] Effectiveness service mode: %MODE%
echo [INFO] Python: %PYEXE%
echo [INFO] Log: %LOGFILE%
echo [INFO] Starting on http://127.0.0.1:18102
echo.

"%PYEXE%" -m services.effectiveness_service.app --host 127.0.0.1 --port 18102 %ARGS% >>"%LOGFILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo [ERROR] Effectiveness service stopped. Exit code: %EXIT_CODE%
echo [ERROR] Log content:
echo ------------------------------------------------------------
type "%LOGFILE%"
echo ------------------------------------------------------------
pause
exit /b %EXIT_CODE%
