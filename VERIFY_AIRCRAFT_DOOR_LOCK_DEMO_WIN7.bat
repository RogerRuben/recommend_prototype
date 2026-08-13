@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "DEMO_DIR=outputs\aircraft_door_lock_data_staff_20260801"
set "EXPECTED_SHA256=ceedb67516fd7e16ce8cd331b7ece93aec95175db48e774e4f4b011c3bf0705f"
set "PACKAGE="
for %%F in ("%DEMO_DIR%\*.zip") do if not defined PACKAGE set "PACKAGE=%%~fF"

if not defined PACKAGE (
  echo [ERROR] Aircraft door lock delivery ZIP was not found under:
  echo         %DEMO_DIR%
  pause
  exit /b 1
)

echo [INFO] Verifying aircraft door lock delivery package...
call "%~dp0VERIFY_PRODUCT_DELIVERY_WIN7.bat" "%PACKAGE%" --expected-sha256 %EXPECTED_SHA256%
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo [ERROR] Verification failed. Do not install this package.
  pause
  exit /b %RC%
)

echo [OK] Package verification passed.
exit /b 0
