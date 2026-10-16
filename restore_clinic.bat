@echo off
title Pawfect Clinic — Disaster Recovery Restore Tool
color 0e

echo ======================================================================
echo           PAWFECT CLINIC — FULL DISASTER RECOVERY RESTORE
echo ======================================================================
echo.
echo This tool restores your complete clinic database, patients, and media files
echo from an encrypted backup archive (.pbf).
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

set /p BACKUP_NAME="Enter backup filename (e.g. pawfect_daily_20260825_210000.pbf) or full path: "

if "%BACKUP_NAME%"=="" (
    echo [ERROR] No backup filename provided.
    pause
    exit /b 1
)

echo.
echo [*] Validating backup and performing full restore...
echo.

.venv\Scripts\python.exe manage.py restore_backup "%BACKUP_NAME%"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Restore failed. Please check the backup filename or encryption key.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo RESTORE COMPLETED SUCCESSFULLY! All records and media are now live.
echo ======================================================================
pause
