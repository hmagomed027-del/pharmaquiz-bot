@echo off
title PharmaQuiz Setup
color 0A

set PYTHON=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe

echo Python: %PYTHON%
"%PYTHON%" --version
if errorlevel 1 (
    echo ERROR: Python not found at expected path.
    pause
    exit /b 1
)

echo.
echo Step 1/2 - Installing libraries (1-3 min)...
"%PYTHON%" -m pip install --upgrade pip --quiet
"%PYTHON%" -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Installation failed. Check internet connection.
    pause
    exit /b 1
)

echo.
echo Step 2/2 - Starting server and bot...
echo ========================================
echo   Server: http://localhost:8000
echo   Set WEBAPP_URL in .env to a public HTTPS
echo   URL (e.g. from ngrok) for Telegram Mini App
echo   Press Ctrl+C to stop.
echo ========================================
echo.
"%PYTHON%" run.py

echo.
echo Stopped.
pause
