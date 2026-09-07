@echo off
setlocal
cd /d "%~dp0\..\.."

if not defined EFFECT_RUNTIME_PACKAGE set "EFFECT_RUNTIME_PACKAGE=%~dp0model\lock_v17_current\lock_v17_runtime_manifest.json"
if not defined EFFECT_LOCK_V17_ADAPTER_CONFIG set "EFFECT_LOCK_V17_ADAPTER_CONFIG=%~dp0config\lock_v17_adapter.json"

if not exist "%EFFECT_RUNTIME_PACKAGE%" (
  echo [ERROR] Lock V17 frozen runtime manifest was not found:
  echo %EFFECT_RUNTIME_PACKAGE%
  echo.
  echo Export lock_v17_reuse_model_DIGEST.zip from the trained V17 application,
  echo extract it to model\lock_v17_current, then retry.
  pause
  exit /b 1
)

if not exist "%EFFECT_LOCK_V17_ADAPTER_CONFIG%" (
  echo [ERROR] Lock V17 adapter config was not found:
  echo %EFFECT_LOCK_V17_ADAPTER_CONFIG%
  echo.
  echo Copy config\lock_v17_adapter.example.json to lock_v17_adapter.json and
  echo replace a/b/c/d, units and ranges with real DataMaster field definitions.
  pause
  exit /b 1
)

if defined EFFECT_SERVICE_PYTHON (
  set "LOCK_V17_PYTHON=%EFFECT_SERVICE_PYTHON%"
) else (
  set "LOCK_V17_PYTHON=python"
)

echo Lock V17 Effectiveness Service
echo Runtime package: %EFFECT_RUNTIME_PACKAGE%
echo Adapter config: %EFFECT_LOCK_V17_ADAPTER_CONFIG%
echo Python: %LOCK_V17_PYTHON%
echo.

"%LOCK_V17_PYTHON%" services\effectiveness_service\app.py --package "%EFFECT_RUNTIME_PACKAGE%" --lock-v17-adapter-config "%EFFECT_LOCK_V17_ADAPTER_CONFIG%" --port 18102
set "LOCK_V17_EXIT=%ERRORLEVEL%"
if not "%LOCK_V17_EXIT%"=="0" (
  echo.
  echo [ERROR] Lock V17 effectiveness service stopped. Exit code: %LOCK_V17_EXIT%
  pause
)
exit /b %LOCK_V17_EXIT%
