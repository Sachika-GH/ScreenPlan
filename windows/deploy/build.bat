@echo off
chcp 65001 >nul
title ScreenPlan Windows Build
echo ========================================
echo   ScreenPlan Windows Agent - Build .exe
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.9+ from https://python.org
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
python --version
echo.

:: Create venv
echo [1/4] Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create venv
    pause
    exit /b 1
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install dependencies
echo [2/4] Installing Python dependencies...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements
    pause
    exit /b 1
)
pip install pyinstaller
echo.

:: Build .exe
echo [3/4] Building ScreenPlan.exe with PyInstaller...
cd /d "%~dp0"
pyinstaller --clean --noconfirm build_exe.spec
if %errorlevel% neq 0 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)
echo.

:: Copy to output
echo [4/4] Copying output...
if exist "..\..\output" (
    copy /Y dist\ScreenPlan.exe "..\..\output\ScreenPlan-v2.0.0-windows.exe" >nul
    echo Copied to output\ScreenPlan-v2.0.0-windows.exe
) else (
    echo .exe built at: dist\ScreenPlan.exe
)
echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo   Run ScreenPlan.exe to launch the tray app.
echo   On first launch, you'll see the setup window.
echo.
pause
