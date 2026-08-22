@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

if not exist "offline_assets\wheelhouse_win7_py38" mkdir "offline_assets\wheelhouse_win7_py38"
echo [INFO] Downloading CPython 3.8 / Windows x64 wheels on the connected build machine.
echo [INFO] Nothing in this script is intended to run on the offline customer machine.
python -m pip download --disable-pip-version-check --only-binary=:all: ^
  --platform win_amd64 --implementation cp --python-version 38 --abi cp38 ^
  --dest "offline_assets\wheelhouse_win7_py38" ^
  --requirement "requirements_offline_py38.txt"
if errorlevel 1 goto failed

python tools\wheelhouse_manifest.py ^
  --wheelhouse "offline_assets\wheelhouse_win7_py38" ^
  --output "offline_assets\wheelhouse_win7_py38\WHEELHOUSE_MANIFEST.json"
if errorlevel 1 goto failed

echo.
echo [PASS] Offline wheelhouse is ready.
echo Next: BUILD_OFFLINE_DELIVERY_PY38.bat
exit /b 0

:failed
echo.
echo [FAIL] Wheel download failed on the build machine.
exit /b 1
