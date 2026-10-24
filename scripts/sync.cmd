@echo off
setlocal

rem Antigravity Sync Windows Launcher
set "SCRIPT_DIR=%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python "%SCRIPT_DIR%sync_manager.py" %*
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py -3 "%SCRIPT_DIR%sync_manager.py" %*
    exit /b %ERRORLEVEL%
)

echo [Antigravity Sync Error] Python не найден в PATH. Установите Python 3: https://python.org
exit /b 1
