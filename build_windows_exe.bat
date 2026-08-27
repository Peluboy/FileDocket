@echo off
echo Building Windows executable...
pip install pyinstaller
pyinstaller --onefile --windowed organize_downloads.py
move dist\organize_downloads.exe FileFlow.exe
rmdir /s /q build
rmdir /s /q dist
del organize_downloads.spec
echo --------------------------------------------------------
echo Success! FileFlow.exe has been created.
echo You can now delete this script and share the .exe file!
echo --------------------------------------------------------
pause
