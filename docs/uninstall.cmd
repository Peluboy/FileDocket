@echo off
REM FileDocket Windows uninstall wrapper for Command Prompt.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-RestMethod -Uri 'https://peluboy.github.io/FileDocket/uninstall.ps1' | Invoke-Expression"
