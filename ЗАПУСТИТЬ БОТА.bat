@echo off
title PharmaQuiz
color 0A

set PYTHON=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe

echo Starting PharmaQuiz...
echo Server: http://localhost:8000
echo Press Ctrl+C to stop.
echo ========================================
echo.
"%PYTHON%" run.py

echo.
echo Stopped.
pause
