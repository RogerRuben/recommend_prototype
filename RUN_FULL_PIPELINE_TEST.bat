@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=logs\full_pipeline_test_console.log"
set "PYEXE="
if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"

if not defined PYEXE (
  echo [ERROR] Python not found.
  echo The window will stay open so the error can be read.
  pause
  exit /b 1
)

echo Running full pipeline test with: %PYEXE%
set PYTHONUTF8=1
%PYEXE% tests\full_pipeline_test.py > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
echo.
if "%RC%"=="0" (
  echo [PASS] Full pipeline test completed.
  echo Report: logs\full_pipeline_test_report.json
) else (
  echo [FAIL] Full pipeline test failed with code %RC%.
  echo Console log: %LOG%
)
echo.
pause
exit /b %RC%
