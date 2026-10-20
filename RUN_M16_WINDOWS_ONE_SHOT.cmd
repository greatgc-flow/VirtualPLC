@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem M16: localhost-only real pymcprotocol evidence collection on Windows.
rem Requirements: Python >=3.11, pytest, pip, Git; clean PR HEAD checkout.
rem Usage: RUN_M16_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\NEW_EVIDENCE_DIR" "40-char HEAD"
rem Or provide a pinned official wheel path in place of AUTO (offline mode).
rem AUTO downloads solely pymcprotocol==0.3.0 from the official PyPI index;
rem its SHA-256 is verified before any Python client code is imported.
rem NEVER upload raw local Windows environment details to PUBLIC GitHub.
cd /d "%~dp0"
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage
python -m scripts.m16_windows_one_shot --wheel "%~1" --output "%~2" --expected-head "%~3"
exit /b %errorlevel%
:usage
echo Usage: RUN_M16_WINDOWS_ONE_SHOT.cmd "AUTO or wheel path" "new evidence directory" "exact 40-character PR HEAD"
exit /b 2
