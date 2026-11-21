@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Open ArchitectOS UI

REM ==========================================================
REM  ARCHITECTOS — SINGLE ENTRY POINT FOR NORMAL USE
REM
REM  The one-time bootstrap token belongs to the launcher process that
REM  creates it. It is never read from, or written to, any file here:
REM  this script only delegates to launcher.py, which generates the token,
REM  passes matching secrets to the Core and UI children, and opens the
REM  resulting URL itself.
REM ==========================================================

cd /d "%~dp0"

set "UI_URL=http://127.0.0.1:3000"
set "STARTUP_BATCH=%~dp0START_ARCHITECTOS.bat"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "MAX_WAIT_SECONDS=60"

set "PYTHON="
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
if not defined PYTHON set "PYTHON=python"

echo.
echo ==========================================
echo          Open ArchitectOS UI
echo ==========================================
echo.

call :ui_ready
if not errorlevel 1 goto already_running

if not exist "%STARTUP_BATCH%" (
    echo ERROR: ArchitectOS startup file was not found:
    echo   "%STARTUP_BATCH%"
    goto failed
)

echo ArchitectOS is not running. Starting it now...
echo The trusted local session will open in your browser automatically.
echo.

REM START_ARCHITECTOS.bat runs launcher.py --open-ui, which starts or
REM verifies the services AND opens this launch's one-time bootstrap URL.
REM Redirecting stdin lets the launcher's final PAUSE return immediately.
call "%STARTUP_BATCH%" <nul

REM ARCHITECTOS_LAUNCHER_RESTART_FRESHNESS_V1 — the launcher's exit code is the
REM ONLY trustworthy success signal. "Port 3000 answers" is not: a stale
REM service from an earlier launch answers too, and that is exactly how this
REM script used to print "ready" and close with no browser and no trusted
REM session.
if errorlevel 1 goto start_failed

echo.
echo Waiting for the UI at %UI_URL% ...
set /a "WAITED=0"

:wait_for_ui
call :ui_ready
if not errorlevel 1 goto done
if !WAITED! geq %MAX_WAIT_SECONDS% goto readiness_failed
timeout /t 1 /nobreak >nul
set /a "WAITED+=1"
goto wait_for_ui

:done
echo.
echo ArchitectOS UI is ready with a trusted local session.
echo If the browser did not open by itself, the launcher printed the URL.
exit /b 0


REM ==========================================================
REM  ALREADY RUNNING
REM
REM  The live Core/UI belong to a previous launch's trust domain. Issuing a
REM  new token against them would fail closed in the browser, and silently
REM  rotating a secret they do not share would be worse. So: ask first.
REM ==========================================================

:already_running
echo ArchitectOS is already running on %UI_URL%.
echo.
echo Its one-time bootstrap token was consumed by the launch that started it,
echo so a new trusted session cannot be issued without restarting the
echo ArchitectOS-owned services. Project data on disk is not affected.
echo.
choice /c YN /n /m "Restart ArchitectOS services now to open a trusted session? [Y/N] "
if errorlevel 2 goto keep_running

echo.
echo Restarting ArchitectOS services...
"%PYTHON%" launcher.py --restart --open-ui

REM ARCHITECTOS_LAUNCHER_RESTART_FRESHNESS_V1 — do not fall through to the
REM readiness poll on a failed restart. Polling would succeed against a stale
REM service and the window would close as if everything was fine.
if errorlevel 1 goto restart_failed

echo.
set /a "WAITED=0"

:wait_after_restart
call :ui_ready
if not errorlevel 1 goto done
if !WAITED! geq %MAX_WAIT_SECONDS% goto readiness_failed
timeout /t 1 /nobreak >nul
set /a "WAITED+=1"
goto wait_after_restart

:keep_running
echo.
echo Left the running services untouched.
echo The UI stays available at %UI_URL% for ordinary use.
echo Coder file writes and packaging need a trusted session from a fresh
echo launch, which this prompt performs when you answer Y.
exit /b 0

:start_failed
echo.
echo ERROR: ArchitectOS did not start correctly.
echo        The launcher reported a failure, so no trusted browser session
echo        was opened and nothing was reused.
echo        Diagnostics: logs\runtime\launcher.log
goto failed

:restart_failed
echo.
echo ERROR: the restart did not produce a trusted ArchitectOS session.
echo        Either the previous services still hold ports 3000/5000, or the
echo        launcher could not issue a bootstrap URL for this launch.
echo        Diagnostics: logs\runtime\launcher.log
goto failed

:readiness_failed
echo.
echo ERROR: ArchitectOS startup did not make the UI reachable within
echo        %MAX_WAIT_SECONDS% seconds at %UI_URL%.
echo Review the launcher output and logs\runtime\ui.log for details.

:failed
echo.
pause
exit /b 1

:ui_ready
"%POWERSHELL_EXE%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%UI_URL%' -TimeoutSec 2 -Proxy $null; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { exit 0 } } catch { }; exit 1" >nul 2>&1
exit /b %errorlevel%
