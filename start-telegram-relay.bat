@echo off
title Telegram Relay - Monorepo Mode
cls

echo ============================================================
echo   Telegram Relay - Monorepo Mode
echo ============================================================
echo.

REM Check if .env exists
if not exist "%~dp0.env" (
    echo [ERROR] File .env not found in %~dp0
    echo.
    echo Please create .env file with your configuration first.
    echo Example: copy from telegram-relay\.env.example
    echo.
    pause
    exit /b 1
)

echo [OK] Found .env file
echo [INFO] Loading configuration...
echo.

REM Change to D:\demo directory
cd /d "%~dp0"

REM Set environment mode
set RELAY_MODE=monorepo

echo [START] Starting Telegram Relay...
echo ============================================================
echo.

REM Run telegram relay
npx tsx D:\openclaude\packages\telegram-relay\bin\standalone.js

echo.
echo ============================================================
echo [STOPPED] Telegram Relay has stopped.
echo.
pause
