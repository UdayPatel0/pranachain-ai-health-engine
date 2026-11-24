@echo off
REM Start VitaLens on Windows: sets up Python, demo accounts, then opens http://localhost:8000
cd /d "%~dp0"
if not exist .venv (
  echo Setting up, first run only...
  python -m venv .venv || (echo Python 3.10+ is needed: https://www.python.org/downloads/ & pause & exit /b 1)
  .venv\Scripts\pip install -q -r requirements.txt
)
if not exist .env copy .env.example .env >nul
if not exist data\accounts.json .venv\Scripts\python scripts\create_accounts.py --demo
echo.
echo VitaLens is running at http://localhost:8000
echo Demo sign-in: PC0989 / vitalens-demo   (also PC0387, PC0560)
echo Close this window to stop.
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
