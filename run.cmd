@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
    copy ".env.example" ".env" >nul
    start "" notepad ".env"
    exit /b 0
)

py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\streamlit run app.py
