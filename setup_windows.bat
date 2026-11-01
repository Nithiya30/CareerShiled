@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo CareerShield - Windows setup
echo =============================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher was not found. Install Python 3.12 from https://www.python.org/downloads/ and enable Add Python to PATH.
  pause
  exit /b 1
)
py -3.12 --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 is recommended. Trying the default Python installation...
  py -3 -m venv .venv
) else (
  py -3.12 -m venv .venv
)
if errorlevel 1 goto failed
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto failed
pip install -r requirements.txt
if errorlevel 1 goto failed
if not exist .env copy .env.example .env >nul
cd frontend
call npm ci
if errorlevel 1 goto failed
cd ..
echo.
echo Setup completed. Next, double-click start_windows.bat.
echo If you use an existing database, this script does not migrate or reset it.
pause
exit /b 0
:failed
echo.
echo Setup failed. Read the error above, check Python 3.12 and Node.js 20.19+ or 22.12+, then try again.
pause
exit /b 1
