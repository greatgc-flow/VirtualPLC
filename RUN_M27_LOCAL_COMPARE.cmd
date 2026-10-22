@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem M27 offline read-only comparison. M26 input must exist; M27 output must NOT exist.
if "%~1"=="" (
  echo Usage: %~nx0 "M26_INPUT" "NEW_M27_OUTPUT" [OPTIONAL_THRESHOLDS_JSON]
  exit /b 2
)
if "%~2"=="" (
  echo Usage: %~nx0 "M26_INPUT" "NEW_M27_OUTPUT" [OPTIONAL_THRESHOLDS_JSON]
  exit /b 2
)
cd /d "%~dp0"
if errorlevel 1 exit /b 2
if "%~3"=="" (
  py -3.11 -m scripts.m27_compare --input "%~1" --out "%~2"
) else (
  py -3.11 -m scripts.m27_compare --input "%~1" --out "%~2" --thresholds-json "%~3"
)
exit /b %ERRORLEVEL%
