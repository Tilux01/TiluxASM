@echo off
title Tilux ASM - Windows Environment Diagnostic
echo ========================================================
echo Running Tilux ASM Windows Environment Diagnostics...
echo ========================================================
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 diagnose_windows.py
    goto done
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    python diagnose_windows.py
    goto done
)

echo [CRITICAL ERROR] Python was not found in PATH or via the py launcher!
echo.
echo Please install Python 3.11 or 3.12 (64-bit) from https://www.python.org/downloads/
echo IMPORTANT: During installation, be sure to check the box:
echo "Add python.exe to PATH"
echo.

:done
echo.
echo Press any key to close this diagnostic window...
pause >nul
