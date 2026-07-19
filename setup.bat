@echo off
title scrcpy Farm v5.0 Installer
color 0A

echo.
echo ==========================================
echo     scrcpy Farm v5.0 - Auto Installer
echo ==========================================
echo.

:: STEP 1: Check if pip works
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo     Python not found. Downloading Python 3.12...
    goto :install_python
)
python -m pip --version >nul 2>&1
if %errorlevel% equ 0 (
    echo     Python + pip OK.
    goto :step2
)
echo     Python found but pip broken. Reinstalling Python...
goto :install_python

:install_python
echo     Downloading Python 3.12.4 installer...
curl -L -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
if %errorlevel% neq 0 (
    echo [ERROR] Download failed. Check internet.
    pause
    exit /b 1
)
echo     Installing Python 3.12 (silent, auto-add to PATH)...
"%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
echo     Waiting for install to finish...
timeout /t 30 /nobreak >nul
del /Q "%TEMP%\python-installer.exe" 2>nul
echo     Python installed.
refreshenv >nul 2>&1
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "PYINSTALLER=%LOCALAPPDATA%\Programs\Python\Python312\Scripts\pyinstaller.exe"
goto :step2

:step2
:: Find pyinstaller path
set PYINSTALLER=
python -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable),'Scripts','pyinstaller.exe'))" > "%TEMP%\pyi_path.txt" 2>nul
set /p PYINSTALLER=<"%TEMP%\pyi_path.txt"
del /Q "%TEMP%\pyi_path.txt" 2>nul
if "%PYINSTALLER%"=="" set PYINSTALLER=python -m PyInstaller

echo [2/5] Installing packages...
python -m pip install PyQt6 av pyinstaller --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo     Retrying with --user flag...
    python -m pip install PyQt6 av pyinstaller --quiet --user --disable-pip-version-check
)
echo     Done.

:: Recalc pyinstaller path after install
python -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable),'Scripts','pyinstaller.exe'))" > "%TEMP%\pyi_path.txt" 2>nul
set /p PYINSTALLER=<"%TEMP%\pyi_path.txt"
del /Q "%TEMP%\pyi_path.txt" 2>nul

echo [3/5] Checking scrcpy...
set SCRCPY_DIR=C:\scrcpy
if exist "%SCRCPY_DIR%\scrcpy.exe" (
    echo     scrcpy already installed.
    goto :step4
)
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
echo     Done.

:step4
echo [4/5] Building scrcpy-farm.exe...
echo     This may take 2-5 minutes...
if exist "%PYINSTALLER%" (
    "%PYINSTALLER%" --onefile --noconsole --name "scrcpy-farm" scrcpy-farm.py --distpath Desktop --clean --noconfirm
) else (
    python -m PyInstaller --onefile --noconsole --name "scrcpy-farm" scrcpy-farm.py --distpath Desktop --clean --noconfirm
)
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

:step5
echo [5/5] Verifying...
if exist "Desktop\scrcpy-farm.exe" (
    echo.
    echo ==========================================
    echo     DONE! scrcpy-farm.exe is on your Desktop
    echo ==========================================
) else (
    echo [ERROR] scrcpy-farm.exe not found on Desktop.
)

pause
