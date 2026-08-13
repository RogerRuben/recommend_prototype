@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "EFFECT_SOURCE_ROOT=%CD%\services\effectiveness_service\original_runtime_demo"
set "EFFECT_WORKBOOK=%EFFECT_SOURCE_ROOT%\data\aircraft_door_lock_demo.xlsx"
set "EFFECT_STATE="
call START_EFFECTIVENESS_SERVICE_WIN7.bat
