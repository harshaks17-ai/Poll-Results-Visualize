@echo off
REM ===================================================================
REM  Poll Results Visualizer - Windows convenience launcher
REM
REM  Usage:  run.bat            (full pipeline)
REM          run.bat dashboard   (launch the dashboard)
REM          run.bat test        (run all tests)
REM ===================================================================
setlocal

set MODE=%1
if "%MODE%"=="" set MODE=all

if /i "%MODE%"=="dashboard" (
    echo Launching the Streamlit dashboard...
    python main.py dashboard
    goto :end
)

if /i "%MODE%"=="test" (
    echo Running pipeline tests...
    python tests\test_pipeline.py
    echo.
    echo Running dashboard smoke test...
    python tests\test_dashboard.py
    goto :end
)

if /i "%MODE%"=="all" (
    echo Running the full pipeline...
    python main.py all
    goto :end
)

echo Unknown mode: %MODE%
echo Usage: run.bat [ all ^| dashboard ^| test ]

:end
endlocal
