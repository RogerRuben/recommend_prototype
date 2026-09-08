@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if exist "runtime\service_runtime.local.bat" call "runtime\service_runtime.local.bat"
if not defined COST_EFFECTIVENESS_HOST set "COST_EFFECTIVENESS_HOST=127.0.0.1"
if not defined COST_EFFECTIVENESS_PORT set "COST_EFFECTIVENESS_PORT=17000"
if not exist "logs" mkdir "logs"
set "LOGFILE=%CD%\logs\cost_effectiveness_service.log"
set "PYTHON_EXE="
if defined COST_EFFECTIVENESS_PYTHON if exist "%COST_EFFECTIVENESS_PYTHON%" set "PYTHON_EXE=%COST_EFFECTIVENESS_PYTHON%"
if not defined PYTHON_EXE if defined MAIN_APP_PYTHON if exist "%MAIN_APP_PYTHON%" set "PYTHON_EXE=%MAIN_APP_PYTHON%"
if not defined PYTHON_EXE if exist "runtime\python38\python.exe" set "PYTHON_EXE=%CD%\runtime\python38\python.exe"
if not defined PYTHON_EXE if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYTHON_EXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYTHON_EXE if exist "runtime\python.exe" set "PYTHON_EXE=%CD%\runtime\python.exe"
if not defined PYTHON_EXE (
  echo [ERROR] Field runtime Python was not found.
  echo Expected runtime\python38\python.exe, runtime\venvs\model_runtime38\Scripts\python.exe,
  echo runtime\python.exe, or COST_EFFECTIVENESS_PYTHON in runtime\service_runtime.local.bat.
  pause
  exit /b 2
)
set "PYTHONUTF8=1"
"%PYTHON_EXE%" -c "import app.price_output; import cost_effectiveness_analysis.app"
if errorlevel 1 (
  echo [ERROR] Runtime preflight failed. Verify the field runtime package and source directory.
  pause
  exit /b 3
)
"%PYTHON_EXE%" tools\check_service_readiness.py --port "%COST_EFFECTIVENESS_PORT%" --service cost-effectiveness-analysis --quiet >nul 2>&1
set "PORT_STATUS=%ERRORLEVEL%"
if "%PORT_STATUS%"=="0" (
  echo [OK] Existing cost-effectiveness service detected.
  exit /b 0
)
if "%PORT_STATUS%"=="2" (
  echo [ERROR] Port %COST_EFFECTIVENESS_PORT% is occupied by another process.
  pause
  exit /b 4
)
echo Starting Cost-Effectiveness Analysis Workbench on http://%COST_EFFECTIVENESS_HOST%:%COST_EFFECTIVENESS_PORT%
echo Runtime: %PYTHON_EXE%
>"%LOGFILE%" echo Cost-effectiveness service startup log
>>"%LOGFILE%" echo Python: %PYTHON_EXE%
>>"%LOGFILE%" echo Started: %DATE% %TIME%
"%PYTHON_EXE%" -m cost_effectiveness_analysis.app --host "%COST_EFFECTIVENESS_HOST%" --port "%COST_EFFECTIVENESS_PORT%" >>"%LOGFILE%" 2>&1
if errorlevel 1 pause
endlocal
