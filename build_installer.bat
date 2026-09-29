@echo off
cd /d "%~dp0"
python build.py || exit /b 1
where ISCC >nul 2>nul
if errorlevel 1 (
  echo Inno Setup Compiler ISCC.exe not found in PATH.
  echo Install Inno Setup from https://jrsoftware.org/isinfo.php
  echo Then run this script again.
  pause
  exit /b 1
)
ISCC installer\ModernPlayer.iss
pause
