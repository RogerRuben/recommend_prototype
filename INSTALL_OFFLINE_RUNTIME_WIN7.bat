@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

set "BASEPY="
if defined PYTHON38_EXE if exist "%PYTHON38_EXE%" set "BASEPY=%PYTHON38_EXE%"
if not defined BASEPY if exist "C:\Python38\python.exe" set "BASEPY=C:\Python38\python.exe"
if not defined BASEPY if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Programs\Python\Python38\python.exe" set "BASEPY=%LOCALAPPDATA%\Programs\Python\Python38\python.exe"
if not defined BASEPY for /f "delims=" %%P in ('where python 2^>nul') do if not defined BASEPY set "BASEPY=%%P"

if not defined BASEPY (
  echo [ERROR] 64-bit Python 3.8 was not found.
  echo Set PYTHON38_EXE to the full path of the customer's Python 3.8 python.exe.
  pause
  exit /b 1
)

"%BASEPY%" -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2]==(3,8) and struct.calcsize('P')==8 else 1)"
if errorlevel 1 (
  echo [ERROR] Selected interpreter is not 64-bit Python 3.8:
  echo %BASEPY%
  pause
  exit /b 1
)

"%BASEPY%" tools\verify_offline_package.py --root "%CD%"
if errorlevel 1 goto failed

set "VENV=%CD%\runtime\venvs\offline_py38"
if not exist "%VENV%\Scripts\python.exe" (
  echo [INFO] Creating isolated offline runtime...
  "%BASEPY%" -m venv "%VENV%"
  if errorlevel 1 goto failed
)

echo [INFO] Installing only from the packaged wheelhouse. Network access is disabled.
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check --no-index ^
  --only-binary=:all: --find-links "%CD%\wheelhouse_win7_py38" ^
  --requirement "%CD%\requirements_offline_py38.txt"
if errorlevel 1 goto failed

echo [INFO] Running real price and effectiveness model smoke tests...
"%VENV%\Scripts\python.exe" tools\verify_model_environment.py --profile runtime --smoke-current-models
if errorlevel 1 goto failed

if not exist "runtime" mkdir "runtime"
>"runtime\service_runtime.local.bat" echo @echo off
>>"runtime\service_runtime.local.bat" echo set "PRICE_SERVICE_PYTHON=%%~dp0venvs\offline_py38\Scripts\python.exe"
>>"runtime\service_runtime.local.bat" echo set "EFFECT_SERVICE_PYTHON=%%~dp0venvs\offline_py38\Scripts\python.exe"
>>"runtime\service_runtime.local.bat" echo set "MAIN_APP_PYTHON=%%~dp0venvs\offline_py38\Scripts\python.exe"

echo.
echo [PASS] Offline runtime is installed and both formal models passed real calculations.
echo Start the complete system with START_OFFLINE_WIN7.bat.
pause
exit /b 0

:failed
echo.
echo [FAIL] Offline runtime installation or model verification failed.
echo No Internet source was used. Check the detailed messages above.
pause
exit /b 1
