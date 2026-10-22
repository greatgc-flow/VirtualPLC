@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem M28 read-only M26 multi-bundle comparison. Output must be NEW/outside repo and inputs.
rem Usage: RUN_M28_COMPARE.cmd "D:\M28_NEW" "D:\M26_RUN_A" "D:\M26_RUN_B" ["D:\M26_RUN_C"]
rem For explicit thresholds or --allow-unequal-runs, use Python CLI documented in docs/M28_PROGRESS.md.
if "%~1"=="" goto usage
if "%~2"=="" goto usage
if "%~3"=="" goto usage
set "OUT=%~1"
shift
set "INPUTS="
:collect
if "%~1"=="" goto run
set "INPUTS=%INPUTS% "%~1""
shift
goto collect
:run
cd /d "%~dp0"
if errorlevel 1 exit /b 2
py -3.11 -m scripts.m28_cross_bundle --out "%OUT%" --inputs %INPUTS%
exit /b %ERRORLEVEL%
:usage
echo Usage: %~nx0 "NEW_M28_OUT" "M26_INPUT_A" "M26_INPUT_B" [M26_INPUT_C ...]
exit /b 2
