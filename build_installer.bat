@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
echo ============================================
echo   NEXUS HOST - build Windows installer
echo ============================================

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.10 or newer is required. Install it from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" / install the py launcher.
  exit /b 1
)

if not exist .venv (
  echo [1/4] Creating virtual environment...
  py -3 -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller || exit /b 1

echo [3/4] Building application with PyInstaller...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
pyinstaller --noconfirm --clean --windowed --name NexusHost --icon assets\nexus.ico --add-data "assets;assets" main.py || exit /b 1

echo [4/4] Building installer with Inno Setup...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo Inno Setup not found. Installing it with winget...
  winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if not defined ISCC (
  echo [ERROR] Could not find Inno Setup. Install it from https://jrsoftware.org/isdl.php and run this script again.
  exit /b 1
)
"%ISCC%" installer\nexushost.iss || exit /b 1

echo.
echo Done. Your installer is here:
dir /b installer_output\*.exe
echo   %CD%\installer_output
endlocal
