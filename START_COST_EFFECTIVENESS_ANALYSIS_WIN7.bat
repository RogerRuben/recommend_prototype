@echo off
setlocal
cd /d "%~dp0"
if not defined COST_EFFECTIVENESS_HOST set "COST_EFFECTIVENESS_HOST=127.0.0.1"
if not defined COST_EFFECTIVENESS_PORT set "COST_EFFECTIVENESS_PORT=17000"
set "PYTHON_EXE=python"
if exist "runtime\python38\python.exe" set "PYTHON_EXE=runtime\python38\python.exe"
echo Starting Cost-Effectiveness Analysis Workbench on http://%COST_EFFECTIVENESS_HOST%:%COST_EFFECTIVENESS_PORT%
"%PYTHON_EXE%" -m cost_effectiveness_analysis.app --host "%COST_EFFECTIVENESS_HOST%" --port "%COST_EFFECTIVENESS_PORT%"
if errorlevel 1 pause
endlocal
