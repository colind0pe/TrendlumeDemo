@echo off
chcp 65001 >nul 2>&1

echo 🚀 Starting Trendlume Web UI...
echo.

uv run streamlit run web/app.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo   [ERROR] Failed to Start Trendlume
    echo ========================================
    echo.
    echo Please make sure your environment is properly configured:
    echo   1. Install uv: https://docs.astral.sh/uv/
    echo   2. Run: uv sync
    echo   3. Run this script again
    echo.
    echo ========================================
    echo.
    pause
)
