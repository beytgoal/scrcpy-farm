@echo off
title scrcpy Farm Installer v5.0
color 0A

echo.
echo ==========================================
echo     scrcpy Farm v5.0 - Windows Installer
echo ==========================================
echo.

:: Find real system Python (not venv)
set PYTHON=
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('python -c "import sys; p=sys.executable; print(p if not p.lower().endswith(('.exe',)) or 'venv' not in p.lower() else '')" 2^>nul') do set PYTHON=%%i
)

:: Fallback: try common Python locations
if "%PYTHON%"=="" (
    for %%p in (
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
        "C:\Python310\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    ) do (
        if exist %%p (
            set PYTHON=%%p
            goto :found_python
        )
    )
    echo [ERROR] No system Python found.
    echo Install Python from python.org with "Add to PATH" checked.
    pause
    exit /b 1
)

:found_python
echo [1/4] Found Python: %PYTHON%

:: Check if pip is available
"%PYTHON%" -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo     pip not found. Installing pip...
    "%PYTHON%" -m ensurepip --upgrade >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Cannot install pip. Install Python with pip included.
        pause
        exit /b 1
    )
)

echo [2/4] Installing packages...
"%PYTHON%" -m pip install PyQt6 av pyinstaller --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo     Done.

:: Find pyinstaller
set PYTHON_DIR=
for /f "tokens=*" %%i in ('"%PYTHON%" -c "import sys,os; print(os.path.dirname(sys.executable))"') do set PYTHON_DIR=%%i
set PYINSTALLER=%PYTHON_DIR%\Scripts\pyinstaller.exe
if not exist "%PYINSTALLER%" set PYINSTALLER=%PYTHON_DIR%\pyinstaller.exe

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
echo     Using: %PYINSTALLER%
echo     This may take 2-5 minutes...
"%PYINSTALLER%" --onefile --noconsole --name "scrcpy-farm" scrcpy-farm.py --distpath Desktop --clean --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. See errors above.
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
