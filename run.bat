@echo off
if exist "DownloadsOrganizer.exe" (
    DownloadsOrganizer.exe
) else (
    echo DownloadsOrganizer.exe not found! Please run build_windows_exe.bat first to build it, or make sure you extracted the zip folder correctly.
    pause
)
