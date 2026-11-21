@echo off
echo ============================================================
echo   ArchitectOS Port 3000 / 5000 Lock Cleaner
echo ============================================================
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    echo Killing orphan UI process on port 3000 (PID %%a)...
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    echo Killing orphan CORE_API process on port 5000 (PID %%a)...
    taskkill /F /PID %%a >nul 2>&1
)
echo Done! Now run "Open ArchitectOS UI" launcher normally.
pause
