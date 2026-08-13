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

echo ============================================================
echo This operation will replace the current price/effect models,
echo back up the current database, and import business data as draft.
echo Stop all three services before continuing.
echo ============================================================
set /p "CONFIRM=Type INSTALL to continue: "
if /I not "%CONFIRM%"=="INSTALL" (
  echo [INFO] Installation cancelled. No files were changed.
  exit /b 2
)

call "%~dp0VERIFY_AIRCRAFT_DOOR_LOCK_DEMO_WIN7.bat"
if errorlevel 1 exit /b %ERRORLEVEL%

call "%~dp0INSTALL_PRODUCT_DELIVERY_WIN7.bat" "%PACKAGE%" --expected-sha256 %EXPECTED_SHA256%
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo [ERROR] Installation failed. Review the output above.
  pause
  exit /b %RC%
)

echo.
echo [OK] Installation finished. Record backup_id and business_release_id.
echo [NEXT] Start services, validate the pending release, then activate it explicitly.
pause
exit /b 0
