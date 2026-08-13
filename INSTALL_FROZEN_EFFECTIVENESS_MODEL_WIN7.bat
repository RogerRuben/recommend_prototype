@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PYEXE="
if exist "runtime\venvs\model_runtime38\Scripts\python.exe" set "PYEXE=%CD%\runtime\venvs\model_runtime38\Scripts\python.exe"
if not defined PYEXE if exist "runtime\python.exe" set "PYEXE=%CD%\runtime\python.exe"
if not defined PYEXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYEXE=%CONDA_PREFIX%\python.exe"
if not defined PYEXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE (echo [ERROR] Python not found.&pause&exit /b 1)

set "MODEL_PACKAGE=%~1"
set "EXPECTED_CODE=%~2"
set "OUTPUT_DIR=%~3"
if not defined OUTPUT_DIR set "OUTPUT_DIR=%CD%\services\effectiveness_service\model\current"
if not defined MODEL_PACKAGE set /p MODEL_PACKAGE=Drag effectiveness_model_*.zip here, then press Enter: 
if not defined EXPECTED_CODE set /p EXPECTED_CODE=Expected product_code - optional, press Enter to skip: 
if not exist "%MODEL_PACKAGE%" (echo [ERROR] Model package not found: "%MODEL_PACKAGE%"&pause&exit /b 2)

set "EXPECTED_ARG="
if defined EXPECTED_CODE set "EXPECTED_ARG=--expected-product-code "%EXPECTED_CODE%""
echo Installing frozen effectiveness model...
"%PYEXE%" -m services.effectiveness_service.install_frozen_effectiveness_model --model-package "%MODEL_PACKAGE%" --output "%OUTPUT_DIR%" %EXPECTED_ARG%
if errorlevel 1 (echo [ERROR] Installation failed. Previous model was preserved.&pause&exit /b 1)
echo [OK] Frozen model installed. Restart START_EFFECTIVENESS_SERVICE_WIN7.bat.
echo [INFO] Legacy Workbook+State packaging remains available through PACKAGE_EFFECTIVENESS_SERVICE_MODEL_WIN7.bat.
pause
