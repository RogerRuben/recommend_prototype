@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYEXE="
if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\venvs\aircraft_door_lock38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\aircraft_door_lock38\Scripts\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"

if not defined PYEXE (
  echo [ERROR] Python was not found.
  echo Run INSTALL_SOURCE_DEPENDENCIES_WIN7.bat first.
  pause
  exit /b 1
)

set "PYTHONUTF8=1"
echo ============================================================
echo GFlowNet candidate experiment - isolated from production UI
echo Python: %PYEXE%
echo Expected duration on this computer: about 1 minute
echo ============================================================
"%PYEXE%" tests\price_boundary_generation_benchmark.py
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [PASS] Experiment completed. See the JSON comparison above.
) else (
  echo [FAIL] Experiment returned code %RC%.
)
pause
exit /b %RC%
