@echo off
chcp 65001 >nul
python run_model_kit_self_test.py
if errorlevel 1 (echo SELF TEST FAILED) else (echo SELF TEST PASS)
pause
