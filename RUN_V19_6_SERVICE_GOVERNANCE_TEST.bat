@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYEXE="
if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (echo Python not found.&pause&exit /b 1)
set PYTHONUTF8=1
"%PYEXE%" tests\v19_6_service_governance_test.py
set RC=%ERRORLEVEL%
pause
exit /b %RC%
