@echo off
chcp 65001 >nul
echo V19.5 模型校验与安全安装。建议先增加 --validate-only。
python validate_and_install_models.py %*
if errorlevel 1 exit /b 1
pause
