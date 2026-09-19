@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [INFO] .env was missing. Created .env from .env.example.
        echo [INFO] Opening .env in notepad. Add your keys, save, and re-run.
        start notepad ".env"
        exit /b 0
    )
)

if not exist ".venv" (
    echo [INFO] Creating virtual environment with py -3...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo [WARN] py -3 failed. Falling back to python -m venv...
        python -m venv .venv
    )
)

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment could not be created or activated.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo [INFO] Installing / updating requirements...
python -m pip install -r requirements.txt

echo [INFO] Launching Streamlit app...
streamlit run app.py
