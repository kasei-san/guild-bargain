@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\streamlit.exe (
    echo ERROR: .venv not found. Run setup.bat first.
    pause
    exit /b 1
)
set PYTHONUTF8=1
.venv\Scripts\streamlit.exe run app.py %*
pause
