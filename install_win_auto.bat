@echo off
set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%~dp0FileFlow.exe"

if not exist "%EXE_PATH%" (
    echo FileFlow.exe not found! Please run build_windows_exe.bat first.
    pause
    exit /b
)

echo Installing background task to run every 15 minutes...
schtasks /create /tn "FileFlow" /tr "\"%EXE_PATH%\"" /sc minute /mo 15 /F
echo --------------------------------------------------------
echo Success! The FileFlow is now running in the background.
echo It will automatically sort files every 15 minutes.
echo You can now close this window.
echo --------------------------------------------------------
pause
