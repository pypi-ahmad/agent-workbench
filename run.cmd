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

set "STREAMLIT_PORT=8590"
for /f %%P in ('powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort %STREAMLIT_PORT% -ErrorAction SilentlyContinue ^| Select-Object -ExpandProperty OwningProcess"') do (
    taskkill /PID %%P /F >nul 2>&1
)

.venv\Scripts\streamlit run app.py --server.port %STREAMLIT_PORT%
