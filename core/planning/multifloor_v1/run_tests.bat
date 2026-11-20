@echo off
echo [ArchitectOS Multi-Floor Engine v1] Running Automated Unit & Auditor Acceptance Suite...
python tests\test_multifloor_engine.py
if %ERRORLEVEL% NEQ 0 (
    echo [FAILED] One or more architectural audit checks failed.
    exit /b %ERRORLEVEL%
)
echo [PASS] All 1-to-N floor scenarios and deterministic audits passed!
python cli.py --scenario all
pause
