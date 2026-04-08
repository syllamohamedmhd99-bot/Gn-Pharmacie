@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo Pharma Cloud ERP - Local Setup (No Docker)
echo ==========================================

:: Check for Python
set "PY_CMD="
if exist "C:\Program Files\Python311\python.exe" (
    set "PY_CMD=C:\Program Files\Python311\python.exe"
) else (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=python"
    ) else (
        py --version >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_CMD=py"
        )
    )
)

if "!PY_CMD!"=="" (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo Using Python command: "!PY_CMD!"

:: Create venv if it doesn't exist
if not exist venv (
    echo [1/4] Creating Virtual Environment...
    "!PY_CMD!" -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment already exists. Skipping creation.
)

echo [2/4] Activating Virtual Environment and Installing Dependencies...
call venv\Scripts\activate
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/4] Configuration Check...
:: Ensure .env exists or use defaults
if not exist .env (
    echo [INFO] .env not found. Creating a default one.
    echo SECRET_KEY=dev-secret-key-12345 > .env
    echo FLASK_ENV=development >> .env
    echo SESSION_TYPE=sqlalchemy >> .env
)

echo [4/4] Starting Application...
echo.
echo ========================================================
echo L'application sera disponible sur : http://localhost:5000
echo ========================================================
echo.
python run.py

pause
