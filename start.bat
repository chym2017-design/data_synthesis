@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

if not exist ".deps_installed" (
    echo [1/2] Installing dependencies...
    python -m pip install --no-index --find-links=wheels -r requirements.txt -q 2>nul
    if %errorlevel% neq 0 (
        echo Offline install failed, trying online...
        python -m pip install -r requirements.txt -q
        if %errorlevel% neq 0 (
            echo [ERROR] Dependency install failed
            pause
            exit /b 1
        )
    )
    echo installed > .deps_installed
    echo       Done
) else (
    echo [1/2] Dependencies already installed, skip
)

echo [2/2] Starting server...
echo       Open http://localhost:8080
echo       Press Ctrl+C to stop
echo ============================================
python -m uvicorn synth_engine.api.main:app --host 0.0.0.0 --port 8080
pause
