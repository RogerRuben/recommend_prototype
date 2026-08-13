@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "BASEPY="
if defined PYTHON38_EXE if exist "%PYTHON38_EXE%" set "BASEPY=%PYTHON38_EXE%"
if not defined BASEPY if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "BASEPY=%CONDA_PREFIX%\python.exe"
if not defined BASEPY for /f "delims=" %%P in ('where python 2^>nul') do if not defined BASEPY set "BASEPY=%%P"

if not defined BASEPY (
  echo [ERROR] Python 3.8 was not found.
  echo Install 64-bit Python 3.8, or set PYTHON38_EXE to python.exe.
  pause
  exit /b 1
)

"%BASEPY%" -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2]==(3,8) and struct.calcsize('P')==8 else 1)"
if errorlevel 1 (
  echo [ERROR] Selected interpreter is not 64-bit Python 3.8: %BASEPY%
  pause
  exit /b 1
)

set "VENV=%CD%\runtime\venvs\model_runtime38"
if not exist "%VENV%\Scripts\python.exe" (
  echo [INFO] Creating runtime environment: %VENV%
  "%BASEPY%" -m venv "%VENV%"
  if errorlevel 1 goto failed
)

echo [INFO] Installing dependencies from the configured pip index.
echo [INFO] This source package contains no wheels. Internet or an internal pip mirror is required.
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check ^
  -r "services\effectiveness_service\requirements_win7.txt" ^
  -r "services\price_service\requirements_win7_exact.txt"
if errorlevel 1 goto failed

"%VENV%\Scripts\python.exe" tools\verify_model_environment.py --profile runtime --smoke-current-models
if errorlevel 1 goto failed

echo.
echo [PASS] Source runtime environment is ready.
echo Start with START_ALL_SERVICES_WIN7.bat.
pause
exit /b 0

:failed
echo.
echo [FAIL] Dependency installation or model verification failed.
echo Configure pip/PIP_INDEX_URL, or provide the dependency wheels separately.
pause
exit /b 1
