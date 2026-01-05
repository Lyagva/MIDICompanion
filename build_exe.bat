@echo off
setlocal enabledelayedexpansion

REM LaunchpadCompanion - one-file EXE build (Windows)
REM - Creates/uses .venv
REM - Installs requirements + pyinstaller
REM - Bundles templates/ and static/
REM Output:
REM   dist\LaunchpadCompanion.exe

cd /d "%~dp0"

REM Avoid file lock issues if the EXE is running.
taskkill /IM LaunchpadCompanion.exe /F >nul 2>&1

echo [1/4] Preparing venv...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create venv. Make sure Python is installed and on PATH.
    exit /b 1
  )
)

set PY=.venv\Scripts\python.exe

echo [2/4] Installing dependencies...
"%PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1

if exist requirements.txt (
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
)

"%PY%" -m pip install pyinstaller
if errorlevel 1 exit /b 1

echo [3/4] Building EXE...
REM PyInstaller --add-data separator on Windows is ';' (SRC;DEST)
REM We bundle Flask templates & static so render_template/url_for work.
"%PY%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --name LaunchpadCompanion ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  main.py

if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo [4/4] Done.
echo EXE: %CD%\dist\LaunchpadCompanion.exe

echo.
echo Notes:
echo - If the EXE can't find templates/static, check that the add-data paths exist.
echo - rtmidi2 may require system MIDI drivers; run the EXE on a machine with them installed.

del /q LaunchpadCompanion.spec >nul 2>&1

endlocal

