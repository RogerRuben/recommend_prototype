@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "TRAIN_PY=runtime\venvs\price_training38\Scripts\python.exe"
if not exist "%TRAIN_PY%" set "TRAIN_PY=runtime\venvs\aircraft_door_lock38\Scripts\python.exe"
if not exist "%TRAIN_PY%" set "TRAIN_PY=python"

echo ============================================================
echo 独立价格服务模型一键训练导出
echo 只需要：历史成品表 + 成品代号
echo 不需要：model-dir、Notebook、固定模型数量、手工权重
echo ============================================================
set /p "PRICE_TABLE=请输入历史成品 CSV/XLSX 完整路径: "
set /p "PRODUCT_CODE=请输入成品代号（必须与效能服务一致）: "
set /p "PRODUCT_NAME=请输入成品名称（可直接回车）: "
set /p "TARGET_COLUMN=请输入价格列名（可直接回车自动识别）: "

if "%PRICE_TABLE%"=="" goto :usage_error
if "%PRODUCT_CODE%"=="" goto :usage_error

if "%TARGET_COLUMN%"=="" goto :auto_target
"%TRAIN_PY%" tools\train_price_service_model.py "%PRICE_TABLE%" "%PRODUCT_CODE%" --output services\price_service\model\price_native_bundle.pkl --product-name "%PRODUCT_NAME%" --target "%TARGET_COLUMN%"
goto :after_train

:auto_target
"%TRAIN_PY%" tools\train_price_service_model.py "%PRICE_TABLE%" "%PRODUCT_CODE%" --output services\price_service\model\price_native_bundle.pkl --product-name "%PRODUCT_NAME%"

:after_train
if errorlevel 1 goto :failed

echo.
echo [完成] 模型已写入 services\price_service\model\price_native_bundle.pkl
echo 请重启 START_PRICE_SERVICE_WIN7.bat，然后运行 CHECK_MODEL_SERVICES.bat。
pause
exit /b 0

:usage_error
echo [失败] 历史成品表和成品代号不能为空。
pause
exit /b 2

:failed
echo [失败] 训练或导出未完成，请查看上方错误。
pause
exit /b 1
