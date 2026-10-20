@echo off
setlocal EnableExtensions
rem M24 bounded loopback-only scenarios: output must be a NEW directory outside the repo.
rem Usage: RUN_M24_LOCAL_MATRIX.cmd "D:\\VPLC_M24_NEW" [seed] [repeats] [delay_ms]
if "%~1"=="" (
    echo Usage: %~nx0 "D:\VPLC_M24_NEW" [seed] [repeats] [delay_ms]
    exit /b 2
)
set "SEED=%~2"
set "REPEATS=%~3"
set "DELAY=%~4"
if "%SEED%"=="" set "SEED=24"
if "%REPEATS%"=="" set "REPEATS=1"
if "%DELAY%"=="" set "DELAY=65"
python -m scripts.m24_scenarios --out "%~1" --seed "%SEED%" --repeats "%REPEATS%" --delay-ms "%DELAY%"
exit /b %errorlevel%
