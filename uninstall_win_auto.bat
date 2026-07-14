@echo off
echo Uninstalling background task...
schtasks /delete /tn "DownloadsOrganizer" /F
echo --------------------------------------------------------
echo Uninstalled! The Downloads Organizer will no longer run automatically.
echo You can now close this window.
echo --------------------------------------------------------
pause
