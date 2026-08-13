@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "BASEPY="
if defined PYTHON38_EXE if exist "%PYTHON38_EXE%" set "BASEPY=%PYTHON38_EXE%"
if not defined BASEPY if exist "runtime\venvs\virtual_product38\Scripts\python.exe" set "BASEPY=%CD%\runtime\venvs\virtual_product38\Scripts\python.exe"
if not defined BASEPY if exist "runtime\venvs\price_training38\Scripts\python.exe" set "BASEPY=%CD%\runtime\venvs\price_training38\Scripts\python.exe"
if not defined BASEPY if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "BASEPY=%CONDA_PREFIX%\python.exe"
if not defined BASEPY for /f "delims=" %%P in ('where python 2^>nul') do if not defined BASEPY set "BASEPY=%%P"

if not defined BASEPY (
  echo [ERROR] Python 3.8 was not found.
  echo Set PYTHON38_EXE to the full path of a 64-bit Python 3.8 python.exe.
  pause
  exit /b 1
)

"%BASEPY%" -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2]==(3,8) and struct.calcsize('P')==8 else 1)"
if errorlevel 1 (
  echo [ERROR] Selected interpreter is not 64-bit Python 3.8: %BASEPY%
  pause
  exit /b 1
)

if not exist "services\price_service\wheelhouse_win7" (
  echo [ERROR] Missing services\price_service\wheelhouse_win7.
  echo Run DOWNLOAD_PRICE_TRAINING_WHEELS_PY38_WIN64.bat on a connected computer first.
  pause
  exit /b 1
)

set "VENV=%CD%\runtime\venvs\price_training38"
echo [INFO] Base Python: %BASEPY%
echo [INFO] Training environment: %VENV%
if not exist "%VENV%\Scripts\python.exe" (
  "%BASEPY%" -m venv "%VENV%"
  if errorlevel 1 goto failed
)

"%VENV%\Scripts\python.exe" -m pip install --no-index ^
  --find-links "services\price_service\wheelhouse_win7" ^
  -r "services\price_service\requirements_training_py38.txt"
if errorlevel 1 goto failed

"%VENV%\Scripts\python.exe" tools\verify_model_environment.py --profile training
if errorlevel 1 goto failed

set "JUPYTER_CONFIG_DIR=%VENV%\jupyter_config"
set "JUPYTER_DATA_DIR=%VENV%\jupyter_data"
set "JUPYTER_PATH=%VENV%\share\jupyter"
if not exist "%JUPYTER_CONFIG_DIR%" mkdir "%JUPYTER_CONFIG_DIR%"
if not exist "%JUPYTER_DATA_DIR%" mkdir "%JUPYTER_DATA_DIR%"
"%VENV%\Scripts\python.exe" -m ipykernel install --prefix "%VENV%" ^
  --name industrial-price-training38 ^
  --display-name "Industrial Price Training (Python 3.8)"
if errorlevel 1 goto failed
"%VENV%\Scripts\python.exe" -m jupyter kernelspec list | findstr /c:"industrial-price-training38" >nul
if errorlevel 1 goto failed

echo.
echo [PASS] Price training environment is ready.
echo Launch Notebook:
echo   "%VENV%\Scripts\python.exe" -m notebook
pause
exit /b 0

:failed
echo.
echo [FAIL] Training environment creation or verification failed.
pause
exit /b 1
