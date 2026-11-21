@echo off
title ArchitectOS - Clean Launch
echo ============================================================
echo   ArchitectOS - clean launch
echo ============================================================
echo.
echo [1/3] Closing every process LISTENING on ports 3000 and 5000...
powershell -NoProfile -Command "$pids = Get-NetTCPConnection -LocalPort 3000,5000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { Write-Host ('    taskkill /F /T /PID ' + $p); taskkill /F /T /PID $p } } else { Write-Host '    nothing was listening on 3000/5000.' }"
echo.
echo [2/3] Removing stale PID files (logs\runtime and data\runtime)...
powershell -NoProfile -Command "Remove-Item '%~dp0logs\runtime\*.pid' -Force -ErrorAction SilentlyContinue; Remove-Item '%~dp0data\runtime\*.pid' -Force -ErrorAction SilentlyContinue; Write-Host '    done.'"
echo.
echo [3/3] Starting the official launcher...
timeout /t 2 /nobreak >nul
echo.
if not exist "%~dp0START_ARCHITECTOS.bat" (
    echo ERROR: START_ARCHITECTOS.bat was not found next to this file.
    pause
    exit /b 1
)
call "%~dp0START_ARCHITECTOS.bat"
