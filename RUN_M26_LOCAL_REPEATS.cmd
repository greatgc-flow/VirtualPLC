@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem M26 local-only evidence. Use a NEW destination for each invocation.
rem Optional: RUN_M26_LOCAL_REPEATS.cmd "D:\VPLC_M26_001" 3 2 0.5 30
set "DEST=%~1"
if "%DEST%"=="" (
    echo Usage: %~nx0 "NEW_DESTINATION" [runs=3] [clients=2] [duration=0.5] [max_cycles=30]
    exit /b 2
)
set "RUNS=%~2"
if "%RUNS%"=="" set "RUNS=3"
set "CLIENTS=%~3"
if "%CLIENTS%"=="" set "CLIENTS=2"
set "DURATION=%~4"
if "%DURATION%"=="" set "DURATION=0.5"
set "CYCLES=%~5"
if "%CYCLES%"=="" set "CYCLES=30"
cd /d "%~dp0"
if errorlevel 1 exit /b 2
py -3.11 -m scripts.m26_multi_run --out "%DEST%" --runs "%RUNS%" --clients "%CLIENTS%" --duration "%DURATION%" --max-cycles "%CYCLES%"
exit /b %ERRORLEVEL%
