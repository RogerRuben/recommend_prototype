@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
set "PYEXE="
if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (echo [ERROR] Python 3.8 not found.&pause&exit /b 1)
set PYTHONUTF8=1
set "NATIVE=services\price_service\model\price_native_bundle.pkl"
if exist "%NATIVE%" (
  echo Starting exact native price service on 18101...
  "%PYEXE%" -m services.price_service.app --host 127.0.0.1 --port 18101 --model "%NATIVE%" --fallback-json "models\price_bundle.json" >> logs\price_service.log 2>&1
) else (
  echo Exact native bundle not found. Starting portable demonstration backend on 18101...
  "%PYEXE%" -m services.price_service.app --host 127.0.0.1 --port 18101 --fallback-json "models\price_bundle.json" >> logs\price_service.log 2>&1
)
