@echo off
setlocal enabledelayedexpansion

set "PYTHON=python"
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "VENV_DIR=%SCRIPT_DIR%venv"

if /i "%1"=="start" goto start
if /i "%1"=="tray"  goto tray
if /i "%1"=="task"  goto task

REM ============================================================
REM ScreenPlan Windows Agent - Install & Virtual Environment Setup
REM Usage:
REM   install.bat          -> Create venv + install deps
REM   install.bat start    -> Start daemon
REM   install.bat tray     -> Start tray app
REM   install.bat task     -> Register Windows scheduled task (auto-start)
REM ============================================================

echo === ScreenPlan Windows Agent Setup ===
echo.

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

REM Create venv
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    %PYTHON% -m venv "%VENV_DIR%"
)

REM Install deps
echo Installing dependencies...
call "%VENV_DIR%\Scripts\activate.bat"
pip install --upgrade pip -q
pip install -r "%PROJECT_DIR%\requirements.txt" -q
echo.

REM Run pywin32 post-install script
echo Running pywin32 post-install setup...
python "%VENV_DIR%\Scripts\pywin32_postinstall.py" -install -silent 2>nul
echo.
echo Done! Setup complete.
echo.
echo   install.bat start    -> Start background tracker
echo   install.bat tray     -> Start system tray
echo   install.bat task     -> Register auto-start (hidden, login)
echo   python main.py setup -> First-time account setup
goto end

:start
call "%VENV_DIR%\Scripts\activate.bat"
python "%PROJECT_DIR%\main.py" daemon
goto end

:tray
call "%VENV_DIR%\Scripts\activate.bat"
python "%PROJECT_DIR%\main.py" tray
goto end

:task
echo Registering Windows scheduled task for auto-start (tray + hidden)...
schtasks /create /tn "ScreenPlanAgent" /tr "wscript.exe \"%SCRIPT_DIR%start_hidden_tray.vbs\"" /sc onlogon /rl highest /f
if %errorlevel% equ 0 (
    echo Task registered. Tray icon will appear on login with auto-tracking enabled.
    echo   schtasks /delete /tn "ScreenPlanAgent" /f   -> Remove task
) else (
    echo ERROR: Failed to register task. Try running as Administrator.
)
goto end

:end
endlocal
