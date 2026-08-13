@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYEXE="
if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
echo ============================================================
echo V19.6 Environment Check
echo Python: %PYEXE%
if not defined PYEXE (echo [ERROR] Python not found.&pause&exit /b 1)
%PYEXE% -c "import sys,sqlite3,json,http.server; print('Version:',sys.version); print('Bits:',8*__import__('struct').calcsize('P')); print('sqlite3: OK'); print('stdlib HTTP: OK'); assert sys.version_info[:2] >= (3,8)"
if errorlevel 1 (echo [ERROR] Environment check failed.) else (echo [OK] Source runtime is ready.)
echo Note: On Windows 7 use a Python 3.8 environment.
echo ============================================================
pause
