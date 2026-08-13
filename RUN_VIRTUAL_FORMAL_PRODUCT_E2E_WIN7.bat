@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=logs\virtual_formal_product_e2e_console.log"
set "PYEXE="

if exist "runtime\venvs\virtual_product38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\virtual_product38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"

if not defined PYEXE (
  echo [ERROR] Python not found.
  echo Install 64-bit Python 3.8 or create runtime\venvs\virtual_product38 first.
  pause
  exit /b 1
)

echo Running virtual formal-product E2E with: %PYEXE%
set PYTHONUTF8=1
"%PYEXE%" tests\virtual_formal_product_e2e_test.py > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
echo.
if "%RC%"=="0" (
  echo [PASS] Virtual formal-product pipeline completed.
  echo Report: logs\virtual_formal_product_e2e_report.json
) else (
  echo [FAIL] Virtual formal-product pipeline failed with code %RC%.
  echo Console log: %LOG%
)
echo.
pause
exit /b %RC%
