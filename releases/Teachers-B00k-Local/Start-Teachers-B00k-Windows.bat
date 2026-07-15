@echo off
setlocal
cd /d "%~dp0backend"

where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required. Install it from https://www.python.org/downloads/ and run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local Teachers B00k environment...
  py -3 -m venv .venv
)

echo Checking local app requirements...
call .venv\Scripts\python.exe -m pip install -q -r requirements-runtime.txt
if errorlevel 1 (
  echo Setup could not finish. The first setup needs an internet connection.
  pause
  exit /b 1
)

echo Starting Teachers B00k at http://127.0.0.1:8010
start "Teachers B00k Server" /B .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8010

echo.
echo Teachers B00k is running locally. Keep this window open while using it.
echo Your data is stored only on this computer in backend\gradebook.db.
pause
