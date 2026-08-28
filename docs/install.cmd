@echo off
REM FileDocket Windows installer wrapper for Command Prompt.
REM curl -fsSL https://peluboy.github.io/FileDocket/install.cmd -o %TEMP%\fd-install.cmd && %TEMP%\fd-install.cmd
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-RestMethod -Uri 'https://peluboy.github.io/FileDocket/install.ps1' | Invoke-Expression"
