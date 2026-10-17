@echo off
cd /d "%~dp0"
title ShenLun Grid
echo Starting ShenLun Grid, the page will open in your browser shortly...
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [NOTICE] Python was not found on this computer.
  echo.
  echo Option A: install Python first
  echo   1. Go to https://www.python.org/downloads/
  echo   2. Run the installer and TICK "Add python.exe to PATH"
  echo   3. Then double-click this file again.
  echo.
  echo Option B: run Build-Exe.bat once to create an exe.
  echo.
  pause
  exit /b
)

python main.py

echo.
echo Program window closed. You may press any key to exit.
pause
