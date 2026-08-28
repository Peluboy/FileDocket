@echo off
REM build_windows_release.bat — run on Windows (or GitHub Actions windows-latest).
REM Output: Output\FileDocket-Setup.exe
setlocal
cd /d "%~dp0"

echo [1/4] Icon
python make_filedocket_ico.py || goto :err

echo [2/4] FileDocket.exe
python -m pip install -q pyinstaller pystray pillow
python -m PyInstaller --noconfirm --clean --onefile --windowed --name FileDocket --icon filedocket.ico --add-data "status_iconTemplate.png;." --hidden-import organize_downloads windows_app.py || goto :err
if not exist "dist\FileDocket.exe" goto :err

echo [3/4] Inno Setup
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else (
    echo ERROR: Inno Setup 6 not found. https://jrsoftware.org/isdl.php
    goto :err
)

echo [4/4] FileDocket-Setup.exe
"%ISCC%" "FileDocket.iss" || goto :err

echo.
echo Share this file with Windows users:
echo    Output\FileDocket-Setup.exe
exit /b 0

:err
echo Build FAILED.
exit /b 1
