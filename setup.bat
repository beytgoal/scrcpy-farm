@echo off
title scrcpy Farm Installer
color 0A

echo.
echo ==========================================
echo     scrcpy Farm v4.0 - Windows Installer
echo ==========================================
echo.

set SCRIPT_DIR=%~dp0

echo [1/6] Checking Python...
python --version 1>nul 2>nul
if errorlevel 1 (
    echo Python NOT found. Downloading...
    curl -sL -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    if exist "%TEMP%\python-installer.exe" (
        echo Installing Python...
        start /wait "%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Shortcuts=0
        del "%TEMP%\python-installer.exe" 2>nul
        echo Python installed. REOPEN this bat file now.
        pause
        exit /b 0
    ) else (
        echo FAILED to download Python. Get it from https://python.org/downloads
        pause
        exit /b 1
    )
)
python --version

echo.
echo [2/6] Installing packages...
python -m pip install pyinstaller ttkbootstrap
if errorlevel 1 (
    echo Retrying with --user...
    python -m pip install --user pyinstaller ttkbootstrap
)
echo.

echo [3/6] Downloading scrcpy...
if not exist "%SCRIPT_DIR%bin" mkdir "%SCRIPT_DIR%bin"
if not exist "%SCRIPT_DIR%bin\scrcpy.exe" (
    curl -sL -o "%TEMP%\scrcpy.zip" "https://github.com/Genymobile/scrcpy/releases/latest/download/scrcpy-win64.zip"
    powershell -command "Expand-Archive -Path '%TEMP%\scrcpy.zip' -DestinationPath '%TEMP%\scrcpy-ext' -Force"
    for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\*.exe" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" 1>nul
    for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\*.dll" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" 1>nul
    del "%TEMP%\scrcpy.zip" 2>nul
    rmdir /s /q "%TEMP%\scrcpy-ext" 2>nul
    echo scrcpy downloaded
) else (
    echo scrcpy already exists
)

echo.
echo [4/6] Downloading ADB...
if not exist "%SCRIPT_DIR%bin\adb.exe" (
    curl -sL -o "%TEMP%\adb.zip" "https://dl.google.com/android/repository/platform-tools_latest_windows.zip"
    powershell -command "Expand-Archive -Path '%TEMP%\adb.zip' -DestinationPath '%TEMP%\adb-ext' -Force"
    copy /y "%TEMP%\adb-ext\platform-tools\adb.exe" "%SCRIPT_DIR%bin\" 1>nul
    copy /y "%TEMP%\adb-ext\platform-tools\AdbWinApi.dll" "%SCRIPT_DIR%bin\" 1>nul
    copy /y "%TEMP%\adb-ext\platform-tools\AdbWinUsbApi.dll" "%SCRIPT_DIR%bin\" 1>nul
    del "%TEMP%\adb.zip" 2>nul
    rmdir /s /q "%TEMP%\adb-ext" 2>nul
    echo ADB downloaded
) else (
    echo ADB already exists
)

echo.
echo [5/6] Building scrcpy-farm.exe...
cd /d "%SCRIPT_DIR%"
python -m PyInstaller --onefile --noconsole --name "scrcpy-farm" --distpath "%SCRIPT_DIR%dist" --clean scrcpy-farm.py
if not exist "%SCRIPT_DIR%dist\scrcpy-farm.exe" (
    echo BUILD FAILED
    pause
    exit /b 1
)

echo.
echo [6/6] Copying to Desktop...
copy /y "%SCRIPT_DIR%dist\scrcpy-farm.exe" "%USERPROFILE%\Desktop\scrcpy-farm.exe" 1>nul
echo DONE!
echo.
echo scrcpy-farm.exe is on your Desktop. Double-click to start.
echo.
pause
