@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "PYEXE="
if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (echo Python not found.&pause&exit /b 1)

set "EFFECT_SOURCE_ROOT="
set "EFFECT_WORKBOOK="
set "EFFECT_STATE="
set "EFFECT_EXPECTED_PRODUCT_CODE="
set "EFFECT_OUTPUT=%CD%\services\effectiveness_service\model\current"
if not "%~1"=="" set "EFFECT_SOURCE_ROOT=%~1"
if not "%~2"=="" set "EFFECT_WORKBOOK=%~2"
if not "%~3"=="" set "EFFECT_STATE=%~3"
if not "%~4"=="" set "EFFECT_EXPECTED_PRODUCT_CODE=%~4"
if not "%~5"=="" set "EFFECT_OUTPUT=%~5"
if not defined EFFECT_SOURCE_ROOT set /p EFFECT_SOURCE_ROOT=Original effectiveness source directory: 
if not defined EFFECT_WORKBOOK set /p EFFECT_WORKBOOK=Project Workbook path: 
if not defined EFFECT_STATE set /p EFFECT_STATE=State JSON path - press Enter for baseline: 
if not defined EFFECT_EXPECTED_PRODUCT_CODE set /p EFFECT_EXPECTED_PRODUCT_CODE=Expected product_code - recommended: 

if not defined EFFECT_SOURCE_ROOT (echo [ERROR] Source directory is empty.&pause&exit /b 2)
if not defined EFFECT_WORKBOOK (echo [ERROR] Workbook path is empty.&pause&exit /b 2)
if not exist "%EFFECT_SOURCE_ROOT%\interactive_project_app.py" (echo [ERROR] Invalid source directory: "%EFFECT_SOURCE_ROOT%"&pause&exit /b 2)
if not exist "%EFFECT_WORKBOOK%" (echo [ERROR] Workbook not found: "%EFFECT_WORKBOOK%"&pause&exit /b 2)
if defined EFFECT_STATE if not exist "%EFFECT_STATE%" (echo [ERROR] State not found: "%EFFECT_STATE%"&pause&exit /b 2)

echo ============================================================
echo Python:        %PYEXE%
echo Source:        %EFFECT_SOURCE_ROOT%
echo Workbook:      %EFFECT_WORKBOOK%
echo State:         %EFFECT_STATE%
echo Expected code: %EFFECT_EXPECTED_PRODUCT_CODE%
echo Output:        %EFFECT_OUTPUT%
echo ============================================================

set "EXPECTED_ARG="
if defined EFFECT_EXPECTED_PRODUCT_CODE set "EXPECTED_ARG=--expected-product-code "%EFFECT_EXPECTED_PRODUCT_CODE%""
"%PYEXE%" -m services.effectiveness_service.package_effectiveness_runtime --source-root "%EFFECT_SOURCE_ROOT%" --workbook "%EFFECT_WORKBOOK%" --state "%EFFECT_STATE%" --output "%EFFECT_OUTPUT%" %EXPECTED_ARG%
if errorlevel 1 (echo [ERROR] Packaging failed.&pause&exit /b 1)
echo [OK] The JSON above is the product_code actually read from the input Workbook.
echo [OK] Packaged model is ready for START_EFFECTIVENESS_SERVICE_WIN7.bat
pause
