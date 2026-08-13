@echo off
chcp 65001 >nul
echo V19.5 价格模型转换。原始价格为元时请传 --target-divisor 10000；已是万元时传 1。
python price_model_export_patch.py %*
if errorlevel 1 exit /b 1
pause
