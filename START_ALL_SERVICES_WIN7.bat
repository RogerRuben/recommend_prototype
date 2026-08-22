@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if exist "runtime\service_runtime.local.bat" call "runtime\service_runtime.local.bat"
if not exist "logs" mkdir "logs"

set "BOOTPY="
if defined MAIN_APP_PYTHON if exist "%MAIN_APP_PYTHON%" set "BOOTPY=%MAIN_APP_PYTHON%"
if not defined BOOTPY if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "BOOTPY=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined BOOTPY if exist "runtime\python.exe" set "BOOTPY=%CD%\runtime\python.exe"
if not defined BOOTPY if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "BOOTPY=%CONDA_PREFIX%\python.exe"
if not defined BOOTPY for /f "delims=" %%P in ('where python 2^>nul') do if not defined BOOTPY set "BOOTPY=%%P"
if not defined BOOTPY (
  echo [ERROR] No Python interpreter was found for startup health checks.
  pause
  exit /b 1
)
set "PYTHONUTF8=1"

echo [INFO] Starting price prediction service...
start "Price Prediction Service" cmd /k call "%CD%\START_PRICE_SERVICE_WIN7.bat"
echo [INFO] Starting effectiveness prediction service...
start "Effectiveness Prediction Service" cmd /k call "%CD%\START_EFFECTIVENESS_SERVICE_WIN7.bat"

echo [INFO] Waiting for service health. Maximum wait: 20 seconds.
for /L %%S in (1,1,20) do (
  timeout /t 1 /nobreak >nul
  "%BOOTPY%" tools\check_service_readiness.py --port 18101 --service price-prediction-service --quiet >nul 2>&1
  set "PRICE_READY=!ERRORLEVEL!"
  "%BOOTPY%" tools\check_service_readiness.py --port 18102 --service effectiveness-prediction-service --quiet >nul 2>&1
  set "EFFECT_READY=!ERRORLEVEL!"
  if "!PRICE_READY!"=="0" if "!EFFECT_READY!"=="0" goto services_healthy
  echo [INFO] Starting services... %%S/20 ^(price=!PRICE_READY!, effectiveness=!EFFECT_READY!^)
)
goto services_failed

:services_healthy
echo [OK] Both services report healthy. Running deployment predictions...
call CHECK_MODEL_SERVICES.bat >"logs\model_service_check.log" 2>&1
if errorlevel 1 goto services_failed
goto services_ready

:services_failed
echo.
echo [ERROR] Model services did not become ready.
echo.
echo === Health Check ===
if exist "logs\model_service_check.log" (type "logs\model_service_check.log") else (echo Deployment verification did not run.)
echo.
echo === Price Service ===
if exist "logs\price_service.log" (type "logs\price_service.log") else (echo No price service log was created.)
echo.
echo === Effectiveness Service ===
if exist "logs\effectiveness_service.log" (type "logs\effectiveness_service.log") else (echo No effectiveness service log was created.)
pause
exit /b 1

:services_ready
echo.
echo [OK] Deployment verification passed.
type "logs\model_service_check.log"
echo [INFO] Starting recommendation system...
set "IPDEMO_AUTH_ENABLED=1"
set "PYEXE="
if defined MAIN_APP_PYTHON if exist "%MAIN_APP_PYTHON%" set "PYEXE=%MAIN_APP_PYTHON%"
if not defined PYEXE if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (
  echo [ERROR] Recommendation Python was not found.
  pause
  exit /b 1
)
if exist "runtime\last_port.txt" del /q "runtime\last_port.txt" >nul 2>&1
start "Recommendation System" cmd /k call "%CD%\START_RECOMMENDATION_WITH_SERVICES_WIN7.bat"

echo [INFO] Waiting for recommendation Portal. Maximum wait: 60 seconds.
for /L %%S in (1,1,60) do (
  timeout /t 1 /nobreak >nul
  if exist "runtime\last_port.txt" (
    set "MAIN_PORT="
    set /p MAIN_PORT=<"runtime\last_port.txt"
    if defined MAIN_PORT (
      "%PYEXE%" -c "from urllib.request import urlopen; r=urlopen('http://127.0.0.1:!MAIN_PORT!/api/health', timeout=2); raise SystemExit(0 if r.getcode()==200 else 1)" >nul 2>&1
      if not errorlevel 1 goto recommendation_ready
    )
  )
  echo [INFO] Waiting for Portal... %%S/60
)

echo [ERROR] Recommendation Portal did not become ready within 60 seconds.
pause
exit /b 1

:recommendation_ready
set "PORTAL_URL=http://127.0.0.1:!MAIN_PORT!/portal"
echo [OK] Opening !PORTAL_URL!
start "" "!PORTAL_URL!"
exit /b 0
