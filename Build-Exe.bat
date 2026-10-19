@echo off
cd /d "%~dp0"
title Build EXE
echo ============================================
echo   ShenLun Grid - Build an EXE (run once)
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found.
  echo.
  echo Please install Python first:
  echo   1. Open https://www.python.org/downloads/
  echo   2. Run the installer and TICK "Add python.exe to PATH"
  echo   3. Re-run this file.
  echo.
  pause
  exit /b
)

echo [1/2] Checking the build tool...
python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
  echo     PyInstaller not found, installing ^(needs network^)...
  python -m pip install pyinstaller
  python -c "import PyInstaller" >nul 2>nul
  if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller is unavailable. Check your network and retry.
    pause
    exit /b
  )
)
echo     OK.

echo.
echo [2/2] Building, please wait 1-2 minutes, do not close this window...
set ICONOPT=
if exist icon.ico set ICONOPT=--icon icon.ico
python -m PyInstaller --onefile --noconsole --clean %ICONOPT% --name ShenLunGrid main.py

echo.
echo ============================================
echo Done. The EXE is here:  dist\ShenLunGrid.exe
echo No black window. Close the browser tab to exit.
echo If Windows says "untrusted": right-click the exe,
echo click Properties, tick "Unblock", then OK.
echo Saved drafts and history go into a folder next to the exe.
echo ============================================
pause
