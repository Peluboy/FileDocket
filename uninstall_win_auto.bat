@echo off
echo Uninstalling background task...
schtasks /delete /tn "FileFlow" /F
echo --------------------------------------------------------
echo Uninstalled! The FileFlow will no longer run automatically.
echo You can now close this window.
echo --------------------------------------------------------
pause
