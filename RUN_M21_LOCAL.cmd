@echo off
setlocal DisableDelayedExpansion
REM One-command local-only verification. Python >=3.11 and pytest are required.
REM Usage: RUN_M21_LOCAL.cmd "D:\VPLC_M21_NEW" [smoke^|core] [timeout_seconds]
REM Use a NEW absolute output directory outside this source repository for every run.
cd /d "%~dp0" || exit /b 2
if "%~1"=="" (
 echo Usage: %~nx0 "ABSOLUTE_NEW_OUTPUT_DIR" [smoke^|core] [timeout_seconds]
 exit /b 2
)
set "MODE=%~2"
if "%MODE%"=="" set "MODE=smoke"
set "LIMIT=%~3"
if "%LIMIT%"=="" set "LIMIT=90"
where py >nul 2>&1
if not errorlevel 1 (
 py -3.11 -m scripts.m21_local_evidence run --output "%~1" --mode "%MODE%" --timeout-seconds "%LIMIT%"
) else (
 python -m scripts.m21_local_evidence run --output "%~1" --mode "%MODE%" --timeout-seconds "%LIMIT%"
)
set "RC=%ERRORLEVEL%"
exit /b %RC%
