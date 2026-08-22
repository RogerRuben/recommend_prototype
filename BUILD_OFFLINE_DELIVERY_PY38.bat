@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

python tools\build_offline_delivery_py38.py ^
  --wheelhouse "offline_assets\wheelhouse_win7_py38" ^
  --output "deliverables\offline_py38"
if errorlevel 1 (
  echo.
  echo [FAIL] Offline delivery build failed.
  echo Run PREPARE_OFFLINE_WHEELHOUSE_PY38.bat first on a connected build machine.
  pause
  exit /b 1
)
echo.
echo [PASS] Offline delivery ZIP is ready under deliverables\offline_py38.
pause
exit /b 0
