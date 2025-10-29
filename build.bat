@echo off
REM Build script for Windows (CMD) using PyInstaller
REM Creates a virtual environment, installs requirements and PyInstaller, then builds a one-file GUI executable.

SETLOCAL ENABLEDELAYEDEXPANSION
echo === Image Resizer Windows Build ===

REM Ensure python is available
where python >nul 2>&1
if errorlevel 1 (
  echo Python not found on PATH. Please install Python 3.x and try again.
  pause
  exit /b 1
)

REM Create venv if missing
if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Upgrading pip and installing dependencies...
python -m pip install --upgrade pip setuptools wheel
if exist requirements.txt (
  pip install -r requirements.txt
)
pip install --upgrade pyinstaller

REM Clean previous build artifacts
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist image_resizer.spec del /q image_resizer.spec

echo Running PyInstaller to create one-file GUI executable...
REM Use --noconsole because this is a tkinter GUI. Change to --console if you want a console window.
pyinstaller --noconfirm --clean --noconsole --onefile --name ImageResizer ^
  --add-data "in;in" --add-data "logs;logs" image_resizer.py

if errorlevel 1 (
  echo.
  echo Build FAILED.
  pause
  exit /b 1
)

echo.
echo Build succeeded. Executable created at dist\ImageResizer.exe
pause
