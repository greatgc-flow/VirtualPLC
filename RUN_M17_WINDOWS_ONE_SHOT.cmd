@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem M17: explicit local-only pinned-client validation; never contacts a real PLC.
rem Usage: RUN_M17_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\VPLC_M17_NEW" "FULL_40_CHAR_PR_HEAD"
rem Offline: replace AUTO with full pinned pymcprotocol 0.3.0 wheel path.
rem Requires Python >= 3.11, pytest 8/9, pip, Git and a CLEAN PR checkout.
rem Optional: set VPLC_PYTHON=py -3.11 (otherwise uses 'python').
rem Keep output/new private: it contains Windows fingerprint and raw evidence.
cd /d "%~dp0"
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage
if "%VPLC_PYTHON%"=="" set "VPLC_PYTHON=python"
rem Preflight output is deliberately separate from new evidence directory.
%VPLC_PYTHON% -m scripts.m17_preflight --wheel "%~1" --output "%~2" --expected-head "%~3" --report "%~2.preflight.json"
if errorlevel 1 exit /b 2
%VPLC_PYTHON% -m scripts.m16_windows_one_shot --wheel "%~1" --output "%~2" --expected-head "%~3"
exit /b %errorlevel%
:usage
echo Usage: RUN_M17_WINDOWS_ONE_SHOT.cmd "AUTO or pinned wheel path" "NEW OUTSIDE REPO directory" "exact PR HEAD"
exit /b 2
