@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set IPDEMO_MODEL_EXECUTION_MODE=local
if not exist logs mkdir logs
set "LOG=logs\startup.log"
set "PYEXE="

if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE for /f "delims=" %%P in ('where py 2^>nul') do if not defined PYEXE set "PYEXE=py -3.8"

if not defined PYEXE (
  echo [ERROR] Python was not found.
  echo Activate a Conda environment first, preferably Python 3.8 on Windows 7.
  pause
  exit /b 1
)

echo ============================================================
echo Industrial Protocol Demo V19.6 - Intelligent Recommendation
echo Python: %PYEXE%
echo Compatibility mode / one port / local models
echo ============================================================
set PYTHONUTF8=1
%PYEXE% -c "import sys,sqlite3; assert sys.version_info[:2] >= (3,8); print('Python:',sys.version); print('sqlite3: OK')" > "%LOG%" 2>&1
if errorlevel 1 (
  type "%LOG%"
  echo [ERROR] Python 3.8 or later with sqlite3 is required.
  pause
  exit /b 1
)
type "%LOG%"
echo Starting recommendation system. The browser will open automatically.
%PYEXE% run_app.py >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo.
echo Application stopped with code %RC%.
type "%LOG%"
pause
exit /b %RC%
