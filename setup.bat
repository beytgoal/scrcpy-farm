@echo off
title scrcpy Farm Installer v5.0
color 0A

echo.
echo ==========================================
echo     scrcpy Farm v5.0 - Windows Installer
echo ==========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install from python.org with "Add to PATH" checked.
    pause
    exit /b 1
)
echo [1/4] Python found.

echo [2/4] Installing Python packages...
pip install PyQt6 av pyinstaller --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed. Try: py -m pip install PyQt6 av pyinstaller
    pause
    exit /b 1
)
echo     Done.

echo [3/4] Checking scrcpy...
set SCRCPY_DIR=C:\scrcpy
if not exist "%SCRCPY_DIR%\scrcpy.exe" (
    echo     Downloading scrcpy v4.1...
    mkdir "%SCRCPY_DIR%" 2>nul
    curl -L -o "%TEMP%\scrcpy.zip" "https://github.com/Genymobile/scrcpy/releases/download/v4.1/scrcpy-win64-v4.1.zip"
    if %errorlevel% neq 0 (
        echo [ERROR] Download failed.
        pause
        exit /b 1
    )
    echo     Extracting...
    powershell -Command "Expand-Archive -Path '%TEMP%\scrcpy.zip' -DestinationPath '%TEMP%\scrcpy_extract' -Force"
    xcopy /E /Y /Q "%TEMP%\scrcpy_extract\scrcpy-win64-v4.1\*" "%SCRCPY_DIR%\" >nul 2>&1
    del /Q "%TEMP%\scrcpy.zip" 2>nul
    rmdir /S /Q "%TEMP%\scrcpy_extract" 2>nul
    echo     scrcpy installed to %SCRCPY_DIR%
) else (
    echo     scrcpy already installed.
)

echo [4/4] Building scrcpy-farm.exe...
echo     This may take 2-5 minutes for first build...
pyinstaller --onefile --noconsole --name "scrcpy-farm" scrcpy-farm.py --distpath Desktop --clean --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. Check errors above.
    echo     Common fix: py -m PyInstaller --onefile --noconsole --name "scrcpy-farm" scrcpy-farm.py --distpath Desktop --clean --noconfirm
    pause
    exit /b 1
)

if exist "Desktop\scrcpy-farm.exe" (
    echo.
    echo ==========================================
    echo     DONE! scrcpy-farm.exe is on your Desktop
    echo ==========================================
) else (
    echo [ERROR] scrcpy-farm.exe not found on Desktop.
)

pause
