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
set SCRCPY_URL=https://github.com/Genymobile/scrcpy/releases/download/v4.1/scrcpy-win64-v4.1.zip

echo [1/4] Checking Python...
python --version 1>nul 2>nul
if errorlevel 1 (
    echo       Python not found. Downloading...
    curl -L -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
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
echo [2/4] Installing packages...
python -m pip install pyinstaller ttkbootstrap
if errorlevel 1 (
    echo       Trying with --user...
    python -m pip install --user pyinstaller ttkbootstrap
    if errorlevel 1 (
        echo       FAILED
        pause
        exit /b 1
    )
)
echo       OK

echo.
echo [3/4] Downloading scrcpy v4.1 (includes adb)...
if not exist "%SCRPCY_DIR%" mkdir "%SCRPCY_DIR%"
if exist "%SCRPCY_DIR%\scrcpy.exe" (
    echo       Already exists. Skipping.
) else (
    echo       Downloading from GitHub...
    curl -L -o "%TEMP%\scrcpy.zip" "%SCRCPY_URL%"
    if errorlevel 1 (
        echo       curl failed. Trying PowerShell...
        powershell -command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%SCRCPY_URL%' -OutFile '%TEMP%\scrcpy.zip' -UseBasicParsing"
    )
    if not exist "%TEMP%\scrcpy.zip" (
        echo       Download FAILED.
        pause
        exit /b 1
    )
    echo       Extracting...
    powershell -command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Expand-Archive -Path '%TEMP%\scrcpy.zip' -DestinationPath '%TEMP%\scrcpy-ext' -Force"
    if errorlevel 1 (
        echo       Extract FAILED. Zip may be corrupt.
        pause
        exit /b 1
    )
    for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\*.exe" 2^>nul') do copy /y "%%f" "%SCRPCY_DIR%\" 1>nul
    for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\*.dll" 2^>nul') do copy /y "%%f" "%SCRPCY_DIR%\" 1>nul
    for /f "delims=" %%f in ('dir /b /s "%TEMP%\scrcpy-ext\scrcpy-server" 2^>nul') do copy /y "%%f" "%SCRPCY_DIR%\" 1>nul
    del "%TEMP%\scrcpy.zip" 2>nul
    rmdir /s /q "%TEMP%\scrcpy-ext" 2>nul
    if exist "%SCRPCY_DIR%\scrcpy.exe" (
        echo       OK: scrcpy.exe + adb.exe + all DLLs
    ) else (
        echo       Install FAILED
        pause
        exit /b 1
    )
)

echo.
echo [4/4] Building scrcpy-farm.exe...
cd /d "%SCRIPT_DIR%"
python -m PyInstaller --onefile --noconsole --name "scrcpy-farm" --distpath "%SCRIPT_DIR%dist" --clean scrcpy-farm.py
if not exist "%SCRIPT_DIR%dist\scrcpy-farm.exe" (
    echo       BUILD FAILED
    pause
    exit /b 1
)
copy /y "%SCRIPT_DIR%dist\scrcpy-farm.exe" "%USERPROFILE%\Desktop\scrcpy-farm.exe" 1>nul
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build" 2>nul
for %%f in ("%SCRIPT_DIR%*.spec") do del "%%f" 2>nul

echo.
echo ==========================================
echo   ALL DONE!
echo.
echo   C:\scrcpy\:
echo     scrcpy.exe, adb.exe, scrcpy-server
echo     SDL3.dll, AdbWinApi.dll, etc
echo.
echo   Desktop: scrcpy-farm.exe
echo ==========================================
echo.
pause
