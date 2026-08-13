@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "logs" mkdir "logs"

echo [INFO] Starting price prediction service...
start "Price Prediction Service" cmd /k call "%CD%\START_PRICE_SERVICE_WIN7.bat"

echo [INFO] Starting effectiveness prediction service...
start "Effectiveness Prediction Service" cmd /k call "%CD%\START_EFFECTIVENESS_SERVICE_WIN7.bat"

echo [INFO] Waiting for both services. Maximum wait: 60 seconds.
for /L %%S in (1,1,30) do (
  timeout /t 2 /nobreak >nul
  call CHECK_MODEL_SERVICES.bat >"logs\model_service_check.log" 2>&1
  if not errorlevel 1 goto services_ready
  echo [INFO] Waiting... %%S/30
)

echo.
echo [ERROR] Model services did not become ready within 60 seconds.
echo [ERROR] Health-check output:
if exist "logs\model_service_check.log" type "logs\model_service_check.log"
echo.
echo [ERROR] Effectiveness-service output:
if exist "logs\effectiveness_service.log" (
  type "logs\effectiveness_service.log"
) else (
  echo No effectiveness log was created.
)
pause
exit /b 1

:services_ready
echo.
echo [OK] Both model services are available.
type "logs\model_service_check.log"
echo [INFO] Starting recommendation system...
call START_RECOMMENDATION_WITH_SERVICES_WIN7.bat
