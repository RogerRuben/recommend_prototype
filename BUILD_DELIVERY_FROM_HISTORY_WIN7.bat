@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if "%~4"=="" (
  echo Usage:
  echo   %~nx0 history.xlsx price_native_bundle.pkl effectiveness_runtime_manifest.json output.zip [product_code] [product_name]
  echo.
  echo Product code/name default to the model Schema when omitted.
  pause
  exit /b 2
)

set "EXTRA="
if not "%~5"=="" set "EXTRA=%EXTRA% --product-code "%~5""
if not "%~6"=="" set "EXTRA=%EXTRA% --product-name "%~6""

call "%~dp0PRODUCT_DELIVERY_WIN7.bat" build ^
  --history-workbook "%~1" ^
  --price-model "%~2" ^
  --effectiveness-package "%~3" ^
  --output "%~4" ^
  --missing-tokens=-1,\,/ %EXTRA%
exit /b %ERRORLEVEL%

