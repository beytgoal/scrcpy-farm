@echo off
REM ================================================================
REM SCRCPY-FARM BUILDER — Windows
REM ================================================================
title Building scrcpy-farm.exe...

echo.
echo ========================================
echo   scrcpy Farm — Windows Build
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/4] Python not found. Downloading...
    curl -o %TEMP%\python-installer.exe -sL https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    start /wait %TEMP%\python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Shortcuts=0
    echo ✅ Python installed
) else (
    echo [1/4] ✅ Python %USERNAME%
)

REM Install PyInstaller
echo [2/4] Installing PyInstaller...
python -m pip install --upgrade pip -q
python -m pip install pyinstaller -q
echo ✅ PyInstaller ready

REM Compile
set SCRIPT_DIR=%~dp0
echo [3/4] Compiling...
pyinstaller --onefile --noconsole --name "scrcpy-farm" "%SCRIPT_DIR%scrcpy-farm.py"

REM Copy to desktop
echo [4/4] Copying to desktop...
copy /Y "dist\scrcpy-farm.exe" "%USERPROFILE%\Desktop\scrcpy-farm.exe" >nul

echo.
echo ========================================
echo   ✅ DONE!
echo   File: %USERPROFILE%\Desktop\scrcpy-farm.exe
echo ========================================
echo.
pause
