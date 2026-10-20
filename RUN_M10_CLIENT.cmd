@echo off
REM VirtualPLC M10 REAL pymcprotocol client gate (Windows cmd compatible).
REM Usage: RUN_M10_CLIENT.cmd "C:\path\pymcprotocol-0.3.0-py3-none-any.whl"
REM The Python tool prints subprocess output and writes the same bytes to console.log.
setlocal
if "%~1"=="" (
 echo ERROR: specify the exact locally downloaded wheel path.
 exit /b 2
)
set "PYTHON_EXE=python"
if not "%VIRTUALPLC_PYTHON%"=="" set "PYTHON_EXE=%VIRTUALPLC_PYTHON%"
"%PYTHON_EXE%" -m scripts.m10_wheel_gate --wheel "%~1" --evidence-dir "m10_client_evidence"
exit /b %ERRORLEVEL%
