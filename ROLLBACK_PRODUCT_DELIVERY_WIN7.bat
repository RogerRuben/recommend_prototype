@echo off
call "%~dp0PRODUCT_DELIVERY_WIN7.bat" rollback %*
exit /b %ERRORLEVEL%
