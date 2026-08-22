@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if exist "runtime\service_runtime.local.bat" call "runtime\service_runtime.local.bat"
set "PYEXE="
if defined MAIN_APP_PYTHON if exist "%MAIN_APP_PYTHON%" set "PYEXE=%MAIN_APP_PYTHON%"
if not defined PYEXE if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (echo Python not found.&pause&exit /b 1)
set PYTHONUTF8=1
%PYEXE% run_app.py --no-browser
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
