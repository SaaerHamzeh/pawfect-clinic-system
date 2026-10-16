@echo off
title Pawfect Clinic — Manual Backup Tool
color 0b

echo ======================================================================
echo           PAWFECT CLINIC — INSTANT ENCRYPTED BACKUP
echo ======================================================================
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

.venv\Scripts\python.exe manage.py run_backup --tag manual
pause
