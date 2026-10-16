@echo off
title Pawfect Clinic — Firewall Setup (One-Time)

:: Self-elevate if not already running as Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ======================================================================
echo       PAWFECT CLINIC — OPENING REQUIRED FIREWALL PORTS
echo ======================================================================
netsh advfirewall firewall add rule name="Pawfect mDNS" dir=in action=allow protocol=UDP localport=5353
netsh advfirewall firewall add rule name="Pawfect HTTP" dir=in action=allow protocol=TCP localport=8000
echo.
echo [OK] Firewall rules added successfully.
echo ======================================================================
pause