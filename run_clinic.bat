@echo off
title Pawfect Clinic Management System
color 0b

echo ======================================================================
echo           PAWFECT VETERINARY CLINIC MANAGEMENT SYSTEM
echo ======================================================================
echo.
echo [*] Checking local environment and database...
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found in .venv!
    echo Please ensure the project was extracted with .venv intact.
    pause
    exit /b 1
)

echo [*] Starting multi-threaded production server...
echo.

.venv\Scripts\python.exe server.py
pause
