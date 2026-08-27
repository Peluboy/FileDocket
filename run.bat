@echo off
if exist "FileDocket.exe" (
    FileDocket.exe
) else (
    echo FileDocket.exe not found! Please run build_windows_exe.bat first to build it, or make sure you extracted the zip folder correctly.
    pause
)
