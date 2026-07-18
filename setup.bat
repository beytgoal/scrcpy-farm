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

echo [1/6] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo       Python not found. Downloading...
    curl -sL -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    if exist "%TEMP%\python-installer.exe" (
        echo       Installing Python...
        start /wait "%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Shortcuts=0
        del "%TEMP%\python-installer.exe"
        echo       Python installed. Please REOPEN this script.
        echo       Press any key after reopening...
        pause >nul
    ) else (
        echo       FAILED to download Python.
        echo       Download manually: https://python.org/downloads/
        echo       IMPORTANT: check "Add Python to PATH" during install!
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo       OK: %%i

echo.
echo [2/6] Installing Python packages...
python -m pip install --quiet --upgrade pip >"%LOG%" 2>&1
python -m pip install --quiet pyinstaller ttkbootstrap >"%LOG%" 2>&1
echo       OK: pyinstaller + ttkbootstrap

echo.
echo [3/6] Downloading scrcpy...
if not exist "%SCRIPT_DIR%bin" mkdir "%SCRIPT_DIR%bin"
if not exist "%SCRIPT_DIR%bin\scrcpy.exe" (
    curl -sL -o "%TEMP%\scrcpy.zip" "https://github.com/Genymobile/scrcpy/releases/latest/download/scrcpy-win64.zip"
    if exist "%TEMP%\scrcpy.zip" (
        powershell -command "Expand-Archive -Path '%TEMP%\scrcpy.zip' -DestinationPath '%TEMP%\scrcpy-ext' -Force"
        for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\scrcpy.exe" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" >nul
        for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\*.dll" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" >nul
        for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\scrcpy-noconsole.exe" 2^>nul') do copy /y "%%f" "%SCRIPT_DIR%bin\" >nul
        rmdir /s /q "%TEMP%\scrcpy-ext" 2>nul
        del "%TEMP%\scrcpy.zip" 2>nul
        echo       OK: scrcpy downloaded
    ) else (
        echo       WARN: scrcpy download failed, will use default path
    )
) else (
    echo       OK: scrcpy already present
)

echo.
echo [4/6] Downloading ADB...
if not exist "%SCRIPT_DIR%bin\adb.exe" (
    curl -sL -o "%TEMP%\adb.zip" "https://dl.google.com/android/repository/platform-tools_latest_windows.zip"
    if exist "%TEMP%\adb.zip" (
        powershell -command "Expand-Archive -Path '%TEMP%\adb.zip' -DestinationPath '%TEMP%\adb-ext' -Force"
        copy /y "%TEMP%\adb-ext\platform-tools\adb.exe" "%SCRIPT_DIR%bin\" >nul
        copy /y "%TEMP%\adb-ext\platform-tools\AdbWinApi.dll" "%SCRIPT_DIR%bin\" >nul
        copy /y "%TEMP%\adb-ext\platform-tools\AdbWinUsbApi.dll" "%SCRIPT_DIR%bin\" >nul
        rmdir /s /q "%TEMP%\adb-ext" 2>nul
        del "%TEMP%\adb.zip" 2>nul
        echo       OK: ADB downloaded
    ) else (
        echo       WARN: ADB download failed, will use default path
    )
) else (
    echo       OK: ADB already present
)

echo.
echo [5/6] Building scrcpy-farm.exe...
cd /d "%SCRIPT_DIR%"
python -m PyInstaller --onefile --noconsole --name "scrcpy-farm" --distpath "%SCRIPT_DIR%dist" --clean scrcpy-farm.py 2>>"%LOG%"
if not exist "%SCRIPT_DIR%dist\scrcpy-farm.exe" (
    echo       BUILD FAILED. Check log: %LOG%
    pause
    exit /b 1
)
echo       OK: scrcpy-farm.exe built

echo.
echo [6/6] Copying to Desktop...
copy /y "%SCRIPT_DIR%dist\scrcpy-farm.exe" "%USERPROFILE%\Desktop\scrcpy-farm.exe" >nul
if errorlevel 1 (
    echo       WARN: Could not copy to Desktop (access denied)
    echo       EXE is at: %SCRIPT_DIR%dist\scrcpy-farm.exe
) else (
    echo       OK: scrcpy-farm.exe on Desktop
)

REM cleanup
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build" 2>nul
for %%f in ("%SCRIPT_DIR%*.spec") do del "%%f" 2>nul

echo.
echo ==========================================
echo   ALL DONE!
echo.
echo   Desktop: scrcpy-farm.exe
echo   bin:     scrcpy.exe + adb.exe
echo.
echo   Double-click scrcpy-farm.exe to start!
echo ==========================================
echo.
pause
