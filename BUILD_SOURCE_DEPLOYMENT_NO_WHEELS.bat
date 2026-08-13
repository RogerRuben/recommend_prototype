@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "OUT=%~1"
if not defined OUT set "OUT=%CD%\deliverables\source_no_wheels"

powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\tools\build_source_deployment_no_wheels.ps1" -OutputDirectory "%OUT%"
if errorlevel 1 (
  echo [FAIL] Source deployment package was not created.
  pause
  exit /b 1
)

echo [PASS] Source deployment package created under: %OUT%
pause
