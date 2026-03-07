@echo off
setlocal

echo =====================================
echo   Code Compare AI - Starting
echo =====================================

if not exist venv (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

if errorlevel 1 (
    echo [ERROR] Could not activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

if not exist .env (
    echo [INFO] .env not found. Creating from .env.example...
    copy .env.example .env > nul
)

echo [INFO] Launching Streamlit...
streamlit run app.py

pause
