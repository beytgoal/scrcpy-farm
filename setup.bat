@echo off
REM ================================================================
REM SCRCPY-FARM v4.0 — WINDOWS ALL-IN-ONE INSTALLER & BUILDER
REM Double-click this file — it does EVERYTHING:
REM   1. Install Python (if missing)
REM   2. Install dependencies (ttkbootstrap, pyinstaller)
REM   3. Download scrcpy + ADB (if missing)
REM   4. Build scrcpy-farm.exe
REM   5. Copy to desktop
REM ================================================================
title scrcpy Farm — Installer & Builder v4.0
color 0A

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║     scrcpy Farm v4.0 — Windows Installer         ║
echo  ║     Modern UI · Auto-Dependencies · 100+ Devices ║
echo  ╚══════════════════════════════════════════════════╝
echo.

set SCRIPT_DIR=%~dp0
set LOG=%TEMP%\scrcpy-farm-build.log
echo Build started %DATE% %TIME% > "%LOG%"

REM ── STEP 1: Check Python ──
echo [1/6] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo       Python not found. Downloading Python 3.11.9...
    curl -sL -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    if exist "%TEMP%\python-installer.exe" (
        echo       Installing Python (this may take 1-2 minutes)...
        start /wait "%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Shortcuts=0
        del "%TEMP%\python-installer.exe"
        echo       ✅ Python installed. You may need to REOPEN this script.
        echo       Press any key after reopening to continue...
        pause >nul
    ) else (
        echo       ❌ Failed to download Python.
        echo       Please install manually from https://python.org/downloads/
        echo       ⚠️ CHECK "Add Python to PATH" during install!
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo       ✅ %%i

REM ── STEP 2: Install pip packages ──
echo [2/6] Installing Python packages...
python -m pip install --quiet --upgrade pip >"%LOG%" 2>&1
python -m pip install --quiet pyinstaller ttkbootstrap >"%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo       Retrying with --user flag...
    python -m pip install --quiet --user pyinstaller ttkbootstrap >"%LOG%" 2>&1
)
echo       ✅ pyinstaller + ttkbootstrap ready

REM ── STEP 3: Download scrcpy ──
echo [3/6] Downloading scrcpy...
if not exist "%SCRIPT_DIR%bin" mkdir "%SCRIPT_DIR%bin"
if not exist "%SCRIPT_DIR%bin\scrcpy.exe" (
    echo       Fetching latest scrcpy release...
    curl -sL -o "%TEMP%\scrcpy.zip" "https://github.com/Genymobile/scrcpy/releases/latest/download/scrcpy-win64.zip"
    if exist "%TEMP%\scrcpy.zip" (
        powershell -command "Expand-Archive -Path '%TEMP%\scrcpy.zip' -DestinationPath '%TEMP%\scrcpy-extract' -Force"
        REM Move files from nested folder
        for /f %%f in ('dir /b /s "%TEMP%\scrcpy-extract\*.exe" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" >nul
        for /f %%f in ('dir /b /s "%TEMP%\scrcpy-extract\*.dll" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" >nul
        for /f %%f in ('dir /b /s "%TEMP%\scrcpy-extract\scrcpy*" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" >nul
        rmdir /s /q "%TEMP%\scrcpy-extract" 2>nul
        del "%TEMP%\scrcpy.zip" 2>nul
        echo       ✅ scrcpy downloaded to bin\
    ) else (
        echo       ⚠️  scrcpy download failed. Will use default path.
    )
) else (
    echo       ✅ scrcpy already present
)

REM ── STEP 4: Download ADB ──
echo [4/6] Downloading ADB (platform-tools)...
if not exist "%SCRIPT_DIR%bin\adb.exe" (
    curl -sL -o "%TEMP%\adb.zip" "https://dl.google.com/android/repository/platform-tools_latest_windows.zip"
    if exist "%TEMP%\adb.zip" (
        powershell -command "Expand-Archive -Path '%TEMP%\adb.zip' -DestinationPath '%TEMP%\adb-extract' -Force"
        copy /y "%TEMP%\adb-extract\platform-tools\adb.exe" "%SCRIPT_DIR%bin\" >nul
        copy /y "%TEMP%\adb-extract\platform-tools\AdbWinApi.dll" "%SCRIPT_DIR%bin\" >nul
        copy /y "%TEMP%\adb-extract\platform-tools\AdbWinUsbApi.dll" "%SCRIPT_DIR%bin\" >nul
        rmdir /s /q "%TEMP%\adb-extract" 2>nul
        del "%TEMP%\adb.zip" 2>nul
        echo       ✅ ADB downloaded to bin\
    ) else (
        echo       ⚠️  ADB download failed. Will use default path.
    )
) else (
    echo       ✅ ADB already present
)

REM ── STEP 5: Build EXE ──
echo [5/6] Building scrcpy-farm.exe...
cd /d "%SCRIPT_DIR%"
python -m PyInstaller --onefile --noconsole --name "scrcpy-farm" --distpath "%SCRIPT_DIR%dist" scrcpy-farm.py 2>"%LOG%"
if %errorlevel% neq 0 (
    echo       ❌ Build failed. Check %LOG%
    pause
    exit /b 1
)
echo       ✅ scrcpy-farm.exe built

REM ── STEP 6: Copy to Desktop ──
echo [6/6] Installing...
if exist "%USERPROFILE%\Desktop\scrcpy-farm.exe" del "%USERPROFILE%\Desktop\scrcpy-farm.exe"
copy /y "%SCRIPT_DIR%dist\scrcpy-farm.exe" "%USERPROFILE%\Desktop\" >nul

REM Also create a launcher .bat next to the exe
(
    echo @echo off
    echo cd /d "%SCRIPT_DIR%"
    echo start "" "%SCRIPT_DIR%dist\scrcpy-farm.exe"
) > "%USERPROFILE%\Desktop\scrcpy-farm-launcher.bat"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║              ✅ INSTALLATION COMPLETE!            ║
echo  ╠══════════════════════════════════════════════════╣
echo  ║                                                    ║
echo  ║  scrcpy-farm.exe  →  Desktop                       ║
echo  ║  scrcpy + adb     →  bin\                          ║
echo  ║                                                    ║
echo  ║  Just double-click scrcpy-farm.exe to start!       ║
echo  ║  First launch auto-downloads dependencies.         ║
echo  ║                                                    ║
echo  ╚══════════════════════════════════════════════════╝
echo.

REM Clean build artifacts
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build" 2>nul
if exist "%SCRIPT_DIR%*.spec" del "%SCRIPT_DIR%*.spec" 2>nul

echo Build log: %LOG%
pause
