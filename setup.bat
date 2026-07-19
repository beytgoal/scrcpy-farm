@echo off
title scrcpy Farm v5.2 Installer
color 0A

echo.
echo ==========================================
echo     scrcpy Farm v5.2 - Auto Installer
echo ==========================================
echo.

:: STEP 1: Python
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 goto :install_python
python -m pip --version >nul 2>&1
if %errorlevel% equ 0 goto :step2

:install_python
echo     Installing Python 3.12...
curl -L -o "%TEMP%\python.exe" "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
"%TEMP%\python.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
timeout /t 30 /nobreak >nul
del "%TEMP%\python.exe" 2>nul
echo     Done.

:step2
set PYTHON=
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    if not "%%i"=="%%i:AppData%%" set PYTHON=%%i
    goto :found_py
)
:found_py
if "%PYTHON%"=="" set PYTHON=python

echo [2/5] Installing packages...
"%PYTHON%" -m pip install PyQt6 pywin32 pyinstaller --quiet --disable-pip-version-check
echo     Done.

:: Find pyinstaller
for /f "tokens=*" %%i in ('"%PYTHON%" -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable),\"Scripts\",\"pyinstaller.exe\"))"') do set PI=%%i

echo [3/5] Checking scrcpy...
set SCRCPY_DIR=C:\scrcpy
if not exist "%SCRCPY_DIR%\scrcpy.exe" (
    echo     Downloading scrcpy v4.1...
    mkdir "%SCRCPY_DIR%" 2>nul
    curl -L -o "%TEMP%\scrcpy.zip" "https://github.com/Genymobile/scrcpy/releases/download/v4.1/scrcpy-win64-v4.1.zip"
    powershell -Command "Expand-Archive -Path '%TEMP%\scrcpy.zip' -DestinationPath '%TEMP%\scrcpy_extract' -Force"
    xcopy /E /Y /Q "%TEMP%\scrcpy_extract\scrcpy-win64-v4.1\*" "%SCRCPY_DIR%\" >nul 2>&1
    del /Q "%TEMP%\scrcpy.zip" 2>nul
    rmdir /S /Q "%TEMP%\scrcpy_extract" 2>nul
    echo     Done.
) else echo     Already installed.

echo [4/5] Building scrcpy-farm.exe...
echo     This may take 2-5 minutes...
if exist "%PI%" (
    "%PI%" --onefile --noconsole --name "scrcpy-farm" scrcpy-farm.py --distpath Desktop --clean --noconfirm
) else (
    "%PYTHON%" -m PyInstaller --onefile --noconsole --name "scrcpy-farm" scrcpy-farm.py --distpath Desktop --clean --noconfirm
)
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

if exist "Desktop\scrcpy-farm.exe" (
    echo.
    echo ==========================================
    echo     DONE! scrcpy-farm.exe on Desktop
    echo ==========================================
)

pause
