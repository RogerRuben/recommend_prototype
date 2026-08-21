@echo off
setlocal EnableExtensions EnableDelayedExpansion
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
set "PYEXE="
if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (
  echo [ERROR] Python 3.8 not found.
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
