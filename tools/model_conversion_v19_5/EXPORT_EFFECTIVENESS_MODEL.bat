@echo off
chcp 65001 >nul
echo V19.5 效能模型转换：输入原工程源码、Workbook和可选匹配State。
python effectiveness_snapshot_export.py %*
if errorlevel 1 exit /b 1
pause
