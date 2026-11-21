@echo off
title ArchitectOS v1.0 RELEASE

echo.
echo ==========================================
echo        ArchitectOS v1.0 RELEASE
echo ==========================================
echo.


REM ------------------------------------------
REM Detect Current Directory
REM ------------------------------------------

cd /d %~dp0

echo Project:
echo %cd%
echo.


REM ------------------------------------------
REM Find Python
REM Prefer the project venv: it holds the deps.
REM The system Python may have no flask/requests.
REM ------------------------------------------

set "PYTHON="

if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

if defined PYTHON echo Using project venv: %PYTHON%

if not defined PYTHON (
    where python >nul 2>nul
    if errorlevel 1 goto nopython
    set "PYTHON=python"
    echo Using system Python: python
)

echo.

echo Python version:
"%PYTHON%" --version

echo.


REM ------------------------------------------
REM Runtime Dependency Check
REM ------------------------------------------

echo Checking ArchitectOS runtime dependencies...

"%PYTHON%" -c "import flask, flask_cors, requests; print('ArchitectOS runtime deps OK')"

if errorlevel 1 (
    echo.
    echo ERROR: Runtime dependencies missing for this interpreter.
    echo Install them with:
    echo   "%PYTHON%" -m pip install flask flask-cors requests
    echo.
    pause
    exit /b 1
)

echo.


REM ------------------------------------------
REM Start ArchitectOS
REM
REM launcher.py starts + verifies:
REM   CORE_API (5000), UI (3000)
REM and detects (never starts):
REM   COMFYUI (8188), OLLAMA (11434)
REM
REM --open-ui makes the launcher open its own one-time trusted-local
REM bootstrap URL in the default browser. The token is generated per launch
REM by launcher.py and is never stored in a file or passed in by this script.
REM ------------------------------------------

echo Starting ArchitectOS runtime...
echo.

"%PYTHON%" launcher.py --open-ui
set "LAUNCH_RC=%ERRORLEVEL%"

echo.

REM ARCHITECTOS_LAUNCHER_RESTART_FRESHNESS_V1 — propagate the launcher's verdict
REM to the caller. OPEN_ARCHITECTOS_UI.bat uses this exit code as its only
REM success signal, so swallowing it here would silently reintroduce the
REM "console closes, nothing opens" failure.
if not "%LAUNCH_RC%"=="0" (
    echo ==========================================
    echo  ERROR: ArchitectOS did not start correctly.
    echo  Launcher exit code: %LAUNCH_RC%
    echo  Diagnostics: logs\runtime\launcher.log
    echo ==========================================
    echo.
    pause
    exit /b %LAUNCH_RC%
)

echo ArchitectOS launcher finished.
echo.

pause
exit /b 0


:nopython

echo.
echo ERROR: Python not found.
echo Please install Python 3.11+
echo.

pause
exit /b 1
