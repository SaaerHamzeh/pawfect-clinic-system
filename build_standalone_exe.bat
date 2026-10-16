@echo off
title Pawfect Clinic — Compile Standalone App (No Source Code)
color 0b

echo ======================================================================
echo           PAWFECT CLINIC — STANDALONE EXE COMPILER
echo ======================================================================
echo.
echo This tool compiles the entire Python source code into a secure
echo standalone executable (PawfectServer.exe) without exposing any .py files.
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv!
    pause
    exit /b 1
)

.venv\Scripts\python.exe scripts\build_exe.py
pause
