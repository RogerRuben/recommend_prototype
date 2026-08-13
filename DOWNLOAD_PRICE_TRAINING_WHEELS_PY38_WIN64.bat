@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYEXE="
if defined PYTHON_EXE if exist "%PYTHON_EXE%" set "PYEXE=%PYTHON_EXE%"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (
  echo [ERROR] A connected Python with pip was not found.
  pause
  exit /b 1
)

if not exist "services\price_service\wheelhouse_win7" mkdir "services\price_service\wheelhouse_win7"

echo [INFO] Downloading Python 3.8 / Win64 binary wheels.
echo [INFO] This script must run on a trusted computer with Internet access.
"%PYEXE%" -m pip download ^
  --only-binary=:all: ^
  --implementation cp ^
  --python-version 38 ^
  --abi cp38 ^
  --platform win_amd64 ^
  --dest "services\price_service\wheelhouse_win7" ^
  -r "services\price_service\requirements_training_py38.txt"
if errorlevel 1 (
  echo [FAIL] Wheel download failed.
  pause
  exit /b 1
)

"%PYEXE%" tools\wheelhouse_manifest.py ^
  --wheelhouse "services\price_service\wheelhouse_win7" ^
  --output "services\price_service\wheelhouse_win7\WHEELHOUSE_MANIFEST.json"
if errorlevel 1 (
  echo [FAIL] Wheelhouse manifest generation failed.
  pause
  exit /b 1
)

echo [PASS] Price runtime/training wheelhouse is ready.
pause
exit /b 0
