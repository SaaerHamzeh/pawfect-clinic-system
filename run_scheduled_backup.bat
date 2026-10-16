@echo off
title Pawfect Clinic — Automated Scheduled Backup Check
color 0b

echo ======================================================================
echo           PAWFECT CLINIC — SCHEDULED AUTO-BACKUP CHECK
echo ======================================================================
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

.venv\Scripts\python.exe manage.py run_scheduled_backup %*
