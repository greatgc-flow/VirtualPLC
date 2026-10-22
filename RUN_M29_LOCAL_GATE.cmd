@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem M29: offline grouped pytest only; never real PLC or external client wheel.
rem Use a NEW output folder OUTSIDE this source checkout.
rem RUN_M29_LOCAL_GATE.cmd "D:\VPLC_M29_NEW" [GROUPS=6] [TIMEOUT_SECONDS=240]
if "%~1"=="" (
  echo Usage: %~nx0 "NEW_OUTPUT_DIR" [GROUPS=6] [TIMEOUT_SECONDS=240]
  exit /b 2
)
set "OUT=%~1"
set "GROUPS=%~2"
if "%GROUPS%"=="" set "GROUPS=6"
set "TIMEOUT=%~3"
if "%TIMEOUT%"=="" set "TIMEOUT=240"
cd /d "%~dp0"
if errorlevel 1 exit /b 2
py -3.11 -m scripts.m29_local_gate --root "%CD%" --out "%OUT%" --groups "%GROUPS%" --timeout "%TIMEOUT%"
exit /b %ERRORLEVEL%
