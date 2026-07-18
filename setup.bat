@echo off
setlocal EnableDelayedExpansion
title scrcpy Farm v4.0 Installer
color 0A

echo.
echo ==========================================
echo     scrcpy Farm v4.0 - Windows Installer
echo ==========================================
echo.

set SCRIPT_DIR=%~dp0
set LOG=%TEMP%\scrcpy-farm-build.log
echo Build started %DATE% %TIME% > "%LOG%"

REM ── STEP 1: Check Python ──
echo [1/6] Checking Python...
python --version 1>nul 2>nul
if errorlevel 1 (
    echo       Python NOT found. Downloading...
    curl -sL -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    if exist "%TEMP%\python-installer.exe" (
        echo       Installing Python (takes 1-2 min)...
        start /wait "%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Shortcuts=0
        del "%TEMP%\python-installer.exe" 2>nul
        echo.
        echo       Python installed.
        echo       IMPORTANT: Close this window, REOPEN setup.bat, then run again.
        echo.
        pause
        exit /b 0
    ) else (
        echo       FAILED to download Python.
        echo       Manual download: https://python.org/downloads/
        echo       CHECK "Add Python to PATH" during install!
        pause
        exit /b 1
    )
)

REM Show python version
for /f "delims=" %%v in ('python --version 2^>^&1') do echo       Found: %%v

REM ── STEP 2: pip install packages ──
echo.
echo [2/6] Installing pip packages...
echo       Running: python -m pip install pyinstaller ttkbootstrap
echo.
python -m pip install pyinstaller ttkbootstrap
if errorlevel 1 (
    echo.
    echo       ERROR: pip install failed. Trying with --user flag...
    python -m pip install --user pyinstaller ttkbootstrap
    if errorlevel 1 (
        echo.
        echo       FAILED to install packages.
        echo       Try manually: pip install pyinstaller ttkbootstrap
        pause
        exit /b 1
    )
)
echo.
echo       OK: Packages installed

REM ── STEP 3: Download scrcpy ──
echo.
echo [3/6] Downloading scrcpy...
if not exist "%SCRIPT_DIR%bin" mkdir "%SCRIPT_DIR%bin"
if not exist "%SCRIPT_DIR%bin\scrcpy.exe" (
    echo       Downloading from GitHub...
    curl -sL -o "%TEMP%\scrcpy.zip" "https://github.com/Genymobile/scrcpy/releases/latest/download/scrcpy-win64.zip"
    if exist "%TEMP%\scrcpy.zip" (
        powershell -command "Expand-Archive -Path '%TEMP%\scrcpy.zip' -DestinationPath '%TEMP%\scrcpy-ext' -Force"
        for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\scrcpy.exe" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" 1>nul
        for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\*.dll" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" 1>nul
        for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\scrcpy-noconsole.exe" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" 1>nul
        rmdir /s /q "%TEMP%\scrcpy-ext" 2>nul
        del "%TEMP%\scrcpy.zip" 2>nul
        echo       OK: scrcpy in bin\
    ) else (
        echo       WARN: Download failed. Will auto-download on first run.
    )
) else (
    echo       OK: scrcpy already exists
)

REM ── STEP 4: Download ADB ──
echo.
echo [4/6] Downloading ADB...
if not exist "%SCRIPT_DIR%bin\adb.exe" (
    curl -sL -o "%TEMP%\adb.zip" "https://dl.google.com/android/repository/platform-tools_latest_windows.zip"
    if exist "%TEMP%\adb.zip" (
        powershell -command "Expand-Archive -Path '%TEMP%\adb.zip' -DestinationPath '%TEMP%\adb-ext' -Force"
        copy /y "%TEMP%\adb-ext\platform-tools\adb.exe" "%SCRIPT_DIR%bin\" 1>nul
        copy /y "%TEMP%\adb-ext\platform-tools\AdbWinApi.dll" "%SCRIPT_DIR%bin\" 1>nul
        copy /y "%TEMP%\adb-ext\platform-tools\AdbWinUsbApi.dll" "%SCRIPT_DIR%bin\" 1>nul
        rmdir /s /q "%TEMP%\adb-ext" 2>nul
        del "%TEMP%\adb.zip" 2>nul
        echo       OK: ADB in bin\
    ) else (
        echo       WARN: Download failed. Will auto-download on first run.
    )
) else (
    echo       OK: ADB already exists
)

REM ── STEP 5: Build EXE ──
echo.
echo [5/6] Building scrcpy-farm.exe (this takes a minute)...
cd /d "%SCRIPT_DIR%"
python -m PyInstaller --onefile --noconsole --name "scrcpy-farm" --distpath "%SCRIPT_DIR%dist" --clean scrcpy-farm.py 2>>"%LOG%"
if not exist "%SCRIPT_DIR%dist\scrcpy-farm.exe" (
    echo.
    echo       BUILD FAILED!
    echo       Check log: %LOG%
    echo.
    pause
    exit /b 1
)
echo       OK: scrcpy-farm.exe built

REM ── STEP 6: Copy to Desktop ──
echo.
echo [6/6] Copying to Desktop...
copy /y "%SCRIPT_DIR%dist\scrcpy-farm.exe" "%USERPROFILE%\Desktop\scrcpy-farm.exe" 1>nul
if errorlevel 1 (
    echo       WARN: Could not copy to Desktop
    echo       EXE location: %SCRIPT_DIR%dist\scrcpy-farm.exe
) else (
    echo       OK: scrcpy-farm.exe is on your Desktop
)

REM ── Cleanup ──
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build" 2>nul
for %%f in ("%SCRIPT_DIR%*.spec") do del "%%f" 2>nul

echo.
echo ==========================================
echo   ALL DONE!
echo.
echo   scrcpy-farm.exe is on your Desktop
echo   Double-click it to start!
echo ==========================================
echo.
pause
