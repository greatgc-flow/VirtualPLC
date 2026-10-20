@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Local-only M22 TCP soak / real server-child RSS observation.
rem Python 3.11 or newer required. Never connects to a physical PLC.
rem Output directory must NOT exist; nothing is overwritten.
rem Usage: RUN_M22_LOCAL_SOAK.cmd "D:\VPLC_M22_NEW" [1,4,8] [150]
if "%~1"=="" (
  echo Usage: %~nx0 "NEW_ABSOLUTE_EVIDENCE_DIR" [CLIENT_STAGES] [ITERATIONS]
  exit /b 2
)
set "M22_CLIENTS=1,4,8"
if not "%~2"=="" set "M22_CLIENTS=%~2"
set "M22_ITERATIONS=150"
if not "%~3"=="" set "M22_ITERATIONS=%~3"
cd /d "%~dp0" || exit /b 2
python -m scripts.m22_soak --out "%~1" --clients "%M22_CLIENTS%" --iterations "%M22_ITERATIONS%"
exit /b %ERRORLEVEL%
