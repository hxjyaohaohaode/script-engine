@echo off
echo ============================================
echo   Starting Script Engine Servers
echo ============================================
echo.

cd /d "c:\Users\LENOVO\Desktop\剧情衍生系统\script-engine\backend"
echo [1/2] Starting Backend Server (port 8000)...
start "Backend Server" cmd /k "python -m uvicorn main:app --port 8000 --reload"

timeout /t 3 /nobreak >nul

cd /d "c:\Users\LENOVO\Desktop\剧情衍生系统\script-engine\frontend"
echo [2/2] Starting Frontend Server (port 5173)...
start "Frontend Server" cmd /k "npm run dev"

echo.
echo ============================================
echo   Servers are starting!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ============================================
timeout /t 10
