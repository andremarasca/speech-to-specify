@echo off
REM Cláusulas Pétreas — full enforcement pipeline (Windows)
REM Usage: scripts\check_all.bat [--continue] [--skip-tests] [--skip-mypy]

setlocal

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

%PYTHON% "%~dp0check_all.py" %*
exit /b %ERRORLEVEL%
