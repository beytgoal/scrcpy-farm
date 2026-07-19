@echo off
title scrcpy Farm Installer v4.0
color 0A

echo.
echo ==========================================
echo     scrcpy Farm v4.0 - Windows Installer
echo ==========================================
echo.

set SCRIPT_DIR=%~dp0
set SCRPCY_DIR=C:\scrcpy

echo [1/6] Checking Python...
python --version 1>nul 2>nul
if errorlevel 1 (
    echo       Python not found. Downloading...
    curl -sL -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    if exist "%TEMP%\python-installer.exe" (
        echo       Installing Python...
        start /wait "%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Shortcuts=0
        del "%TEMP%\python-installer.exe" 2>nul
        echo       Python installed. Please REOPEN this bat file.
        pause
        exit /b 0
    ) else (
        echo       FAILED. Download manually from https://python.org/downloads
        pause
        exit /b 1
    )
)
for /f "delims=" %%v in ('python --version 2^>^&1') do echo       %%v

echo.
echo [2/6] Installing packages...
python -m pip install pyinstaller ttkbootstrap
if errorlevel 1 (
    echo       Trying with --user...
    python -m pip install --user pyinstaller ttkbootstrap
    if errorlevel 1 (
        echo       FAILED. Run: pip install pyinstaller ttkbootstrap
        pause
        exit /b 1
    )
)
echo       OK

echo.
echo [3/6] Setting up scrcpy...
if not exist "%SCRPCY_DIR%" mkdir "%SCRPCY_DIR%"
if not exist "%SCRPCY_DIR%\scrcpy.exe" (
    echo       Downloading scrcpy...
    curl -sL -o "%TEMP%\scrcpy.zip" "https://github.com/Genymobile/scrcpy/releases/latest/download/scrcpy-win64.zip"
    if exist "%TEMP%\scrcpy.zip" (
        powershell -command "Expand-Archive -Path '%TEMP%\scrcpy.zip' -DestinationPath '%TEMP%\scrcpy-ext' -Force"
        for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\*.exe" 2^>nul') do copy /y "%%f" "%SCRPCY_DIR%\" 1>nul
        for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\*.dll" 2^>nul') do copy /y "%%f" "%SCRPCY_DIR%\" 1>nul
        del "%TEMP%\scrcpy.zip" 2>nul
        rmdir /s /q "%TEMP%\scrcpy-ext" 2>nul
        echo       OK
    ) else (
        echo       Download failed
    )
) else (
    echo       Already exists
)

echo.
echo [4/6] Setting up ADB...
if not exist "%SCRPCY_DIR%\adb.exe" (
    echo       Downloading ADB...
    curl -sL -o "%TEMP%\adb.zip" "https://dl.google.com/android/repository/platform-tools_latest_windows.zip"
    if exist "%TEMP%\adb.zip" (
        powershell -command "Expand-Archive -Path '%TEMP%\adb.zip' -DestinationPath '%TEMP%\adb-ext' -Force"
        copy /y "%TEMP%\adb-ext\platform-tools\adb.exe" "%SCRPCY_DIR%\" 1>nul
        copy /y "%TEMP%\adb-ext\platform-tools\AdbWinApi.dll" "%SCRPCY_DIR%\" 1>nul
        copy /y "%TEMP%\adb-ext\platform-tools\AdbWinUsbApi.dll" "%SCRPCY_DIR%\" 1>nul
        del "%TEMP%\adb.zip" 2>nul
        rmdir /s /q "%TEMP%\adb-ext" 2>nul
        echo       OK
    ) else (
        echo       Download failed
    )
) else (
    echo       Already exists
)

echo.
echo [5/6] Building scrcpy-farm.exe...
cd /d "%SCRIPT_DIR%"
python -m PyInstaller --onefile --noconsole --name "scrcpy-farm" --distpath "%SCRIPT_DIR%dist" --clean scrcpy-farm.py
if not exist "%SCRIPT_DIR%dist\scrcpy-farm.exe" (
    echo       BUILD FAILED
    pause
    exit /b 1
)

echo.
echo [6/6] Done!
copy /y "%SCRIPT_DIR%dist\scrcpy-farm.exe" "%USERPROFILE%\Desktop\scrcpy-farm.exe" 1>nul
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build" 2>nul
for %%f in ("%SCRIPT_DIR%*.spec") do del "%%f" 2>nul

echo.
echo ==========================================
echo   ALL DONE!
echo.
echo   Desktop: scrcpy-farm.exe
echo   C:\scrcpy: scrcpy.exe + adb.exe
echo ==========================================
echo.
pause
