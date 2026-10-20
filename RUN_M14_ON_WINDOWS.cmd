@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem M14: run only on a local Windows development PC. Never use a real PLC endpoint.
rem Usage: RUN_M14_ON_WINDOWS.cmd "C:\path\pymcprotocol-0.3.0-py3-none-any.whl" "D:\new-evidence-dir" "40-char Git commit SHA"
rem Requires Python >=3.11, pytest, git; checkout must be clean and at supplied Git HEAD.
cd /d "%~dp0"
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage
python -m scripts.m14_windows_evidence --wheel "%~1" --output "%~2" --expected-head "%~3"
exit /b %errorlevel%
:usage
echo Usage: RUN_M14_ON_WINDOWS.cmd "wheel path" "new evidence dir (outside repo)" "exact git SHA"
exit /b 2
