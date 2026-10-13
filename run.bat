@echo off
title AutoSub (Backend + Frontend)
cd /d "%~dp0"

:: 1. Cek file .env
if not exist .env (
    if exist env.example (
        copy env.example .env >nul
        echo [INFO] File .env belum ada. Dibuat otomatis dari env.example.
    ) else if exist .env.example (
        copy .env.example .env >nul
        echo [INFO] File .env belum ada. Dibuat otomatis dari .env.example.
    )
)

:: 2. Cek backend virtual environment
if not exist "backend\.venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment backend belum ditemukan di backend\.venv.
    echo Silakan buat venv terlebih dahulu di folder backend.
    echo.
    pause
    exit /b 1
)

:: 3. Cek node_modules frontend
if not exist "frontend\node_modules" (
    echo [INFO] Menginstal dependensi frontend npm...
    cd /d "%~dp0frontend"
    call npm install
    cd /d "%~dp0"
)

:: 4. Jalankan Backend dan Frontend di 1 Terminal yang Sama
"backend\.venv\Scripts\python.exe" launcher.py

if errorlevel 1 (
    echo.
    echo [INFO] AutoSub telah berhenti.
    pause
)
