@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
if not exist frontend\node_modules (
  echo Frontend dependencies are missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
start "CareerShield Backend" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000"
start "CareerShield Frontend" /D "%~dp0frontend" cmd /k "npm run dev -- --host 127.0.0.1"
echo CareerShield is starting.
echo Frontend: http://127.0.0.1:5173
echo Backend API docs: http://127.0.0.1:8000/docs
echo Close the two opened terminal windows to stop the services.
timeout /t 5 >nul
start "" http://127.0.0.1:5173
