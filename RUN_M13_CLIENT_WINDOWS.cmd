@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem M13 opt-in test harness: localhost-only, no connection to physical PLC.
rem No PowerShell required. Compatible with Windows cmd.exe.
rem Usage: RUN_M13_CLIENT_WINDOWS.cmd [EVIDENCE_DIRECTORY]
cd /d "%~dp0"
set "WHEEL_DIR=%CD%\_local_wheel"
if "%~1"=="" (set "EVIDENCE_DIR=%CD%\_local_client_evidence") else (set "EVIDENCE_DIR=%~1")
if exist "%EVIDENCE_DIR%" (
    echo ERROR: Evidence directory exists. Refusing overwrite.
    exit /b 2
)
if not exist "%WHEEL_DIR%" mkdir "%WHEEL_DIR%"
if errorlevel 1 exit /b 2
rem Official SHA-256 verification is mandatory inside m10_wheel_gate.py.
python -m pip download --disable-pip-version-check --no-deps --only-binary=:all: --dest "%WHEEL_DIR%" pymcprotocol==0.3.0
if errorlevel 1 (
    echo ERROR: Official PyPI wheel download failed. Tests NOT_RUN.
    exit /b 2
)
python -m scripts.m10_wheel_gate --wheel "%WHEEL_DIR%\pymcprotocol-0.3.0-py3-none-any.whl" --evidence-dir "%EVIDENCE_DIR%"
set "EXITCODE=%errorlevel%"
if not "%EXITCODE%"=="0" (
    echo ERROR: Wheel verification or client tests failed. Release HOLD.
    exit /b %EXITCODE%
)
echo Test artifacts created in "%EVIDENCE_DIR%". An independent review is still required.
exit /b 0
