@echo off
setlocal EnableExtensions DisableDelayedExpansion
REM Opt-in local-only test. Python 3.11+ required. Does not contact any PLC.
REM Usage: RUN_M23_LOCAL_RECOVERY.cmd "D:\VPLC_M23_FRESH" [clients] [duration_sec] [max_cycles] [delay_ms]
REM Output path MUST NOT exist before invoking. Raw console is saved as console.log.
if "%~1"=="" (
    echo Usage: %~nx0 "D:\VPLC_M23_FRESH" [clients] [duration_sec] [max_cycles] [delay_ms]
    endlocal & exit /b 2
)
set "OUT=%~1"
set "CLIENTS=4"
set "DURATION=2"
set "CYCLES=200"
set "DELAY=45"
if not "%~2"=="" set "CLIENTS=%~2"
if not "%~3"=="" set "DURATION=%~3"
if not "%~4"=="" set "CYCLES=%~4"
if not "%~5"=="" set "DELAY=%~5"
cd /d "%~dp0"
if errorlevel 1 (
    echo Cannot switch to repository directory.
    endlocal & exit /b 2
)
python -m scripts.m23_recovery_soak --out "%OUT%" --clients "%CLIENTS%" --duration "%DURATION%" --max-cycles "%CYCLES%" --delay-ms "%DELAY%"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
