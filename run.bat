@echo off
if exist "FileFlow.exe" (
    FileFlow.exe
) else (
    echo FileFlow.exe not found! Please run build_windows_exe.bat first to build it, or make sure you extracted the zip folder correctly.
    pause
)
