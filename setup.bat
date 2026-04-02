@echo off
cd /d "%~dp0"
set PYTHONUTF8=1

echo Setup started: %date% %time% > setup.log

echo [1/3] python -m venv .venv
echo [1/3] python -m venv .venv >> setup.log 2>&1
python -m venv .venv >> setup.log 2>&1
if errorlevel 1 (
    echo ERROR: python -m venv failed. See setup.log for details.
    pause
    exit /b 1
)
echo OK

echo [2/3] activate
call .venv\Scripts\activate.bat

echo [3/3] pip install -r requirements.txt
echo [3/3] pip install -r requirements.txt >> setup.log 2>&1
.venv\Scripts\pip.exe install -r requirements.txt >> setup.log 2>&1
if errorlevel 1 (
    echo ERROR: pip install failed. See setup.log for details.
    pause
    exit /b 1
)
echo OK

echo.
echo Setup complete. Run run.bat to start.
echo Setup complete. >> setup.log 2>&1
pause
