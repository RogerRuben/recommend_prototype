@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist "runtime\service_runtime.local.bat" call "runtime\service_runtime.local.bat"
if not exist "logs" mkdir "logs"
set "LOGFILE=%CD%\logs\price_service.log"
set "RESULTFILE=%CD%\logs\price_runtime.selected"
set "NATIVE=%CD%\services\price_service\model\price_native_bundle.pkl"
>"%LOGFILE%" echo Price service startup
>>"%LOGFILE%" echo.
>>"%LOGFILE%" echo Started:
>>"%LOGFILE%" echo %DATE% %TIME%

set "BOOTPY="
if defined PRICE_SERVICE_PYTHON if exist "%PRICE_SERVICE_PYTHON%" set "BOOTPY=%PRICE_SERVICE_PYTHON%"
if not defined BOOTPY if exist "runtime\venvs\price_runtime\Scripts\python.exe" set "BOOTPY=%CD%\runtime\venvs\price_runtime\Scripts\python.exe"
if not defined BOOTPY if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "BOOTPY=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined BOOTPY if exist "runtime\python.exe" set "BOOTPY=%CD%\runtime\python.exe"
if not defined BOOTPY if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "BOOTPY=%CONDA_PREFIX%\python.exe"
if not defined BOOTPY for /f "delims=" %%P in ('where python 2^>nul') do if not defined BOOTPY set "BOOTPY=%%P"
if not defined BOOTPY (
  >>"%LOGFILE%" echo Runtime smoke: FAIL
  >>"%LOGFILE%" echo Reason: No Python interpreter was found.
  goto startup_failed
)

set "PYTHONUTF8=1"
"%BOOTPY%" tools\check_service_readiness.py --port 18101 --service price-prediction-service --quiet >nul 2>&1
set "PORT_STATUS=%ERRORLEVEL%"
if "%PORT_STATUS%"=="0" (
  >>"%LOGFILE%" echo.
  >>"%LOGFILE%" echo Existing price service: PASS
  >>"%LOGFILE%" echo Reusing price-prediction-service on 127.0.0.1:18101
  echo [OK] Existing price service detected.
  exit /b 0
)
if "%PORT_STATUS%"=="2" (
  >>"%LOGFILE%" echo.
  >>"%LOGFILE%" echo Runtime smoke: NOT RUN
  >>"%LOGFILE%" echo Reason: Port 18101 is occupied by another process.
  echo [ERROR] Port 18101 is occupied by another process.
  goto startup_failed
)

if not exist "%NATIVE%" (
  >>"%LOGFILE%" echo.
  >>"%LOGFILE%" echo Runtime smoke: FAIL
  >>"%LOGFILE%" echo Reason: Native price model does not exist: %NATIVE%
  goto startup_failed
)

if exist "%RESULTFILE%" del /q "%RESULTFILE%" >nul 2>&1
"%BOOTPY%" tools\select_price_runtime.py --root "%CD%" --model "%NATIVE%" --log "%LOGFILE%" --result-file "%RESULTFILE%"
if errorlevel 1 goto startup_failed
set "PRICEPY="
set /p PRICEPY=<"%RESULTFILE%"
if not defined PRICEPY goto startup_failed

>>"%LOGFILE%" echo.
>>"%LOGFILE%" echo Starting HTTP service
>>"%LOGFILE%" echo 127.0.0.1:18101
echo [OK] Price runtime smoke passed.
echo [INFO] Python: %PRICEPY%
echo [INFO] Model: %NATIVE%
echo [INFO] Log: %LOGFILE%
echo [INFO] Starting on http://127.0.0.1:18101
"%PRICEPY%" -m services.price_service.app --host 127.0.0.1 --port 18101 --model "%NATIVE%" >>"%LOGFILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" exit /b 0
goto service_stopped

:startup_failed
set "EXIT_CODE=1"
echo.
echo [ERROR] Price service startup failed.
goto show_failure

:service_stopped
echo.
echo [ERROR] Price service stopped. Exit code: %EXIT_CODE%

:show_failure
echo Python:
if defined PRICEPY (echo %PRICEPY%) else (echo %BOOTPY%)
echo.
echo Model:
echo %NATIVE%
echo.
echo Reason and detailed log:
echo %LOGFILE%
echo ------------------------------------------------------------
type "%LOGFILE%"
echo ------------------------------------------------------------
echo Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
