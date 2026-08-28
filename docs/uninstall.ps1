# FileDocket Windows uninstall.
# PowerShell: irm https://peluboy.github.io/FileDocket/uninstall.ps1 | iex
# Command Prompt: powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://peluboy.github.io/FileDocket/uninstall.ps1 | iex"
# Does not delete organized files. Does not delete %USERPROFILE%\.file-organizer (settings, or a local git clone).

$ErrorActionPreference = "Continue"
if ($env:OS -ne "Windows_NT") {
    Write-Host "This uninstall script is for Windows."
    Write-Host "macOS: curl -fsSL https://peluboy.github.io/FileDocket/uninstall.sh | bash"
    return
}

Get-Process -Name "FileDocket" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$dest = Join-Path $env:LOCALAPPDATA "FileDocket"
$unins = Join-Path $dest "unins000.exe"
if (Test-Path $unins) {
    Start-Process -FilePath $unins -ArgumentList "/VERYSILENT","/NORESTART","/SUPPRESSMSGBOXES" -Wait
}

& schtasks.exe /delete /tn "FileDocket" /f 2>$null | Out-Null

$links = @(
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\FileDocket.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\FileDocket.lnk"),
    (Join-Path $env:USERPROFILE "Desktop\FileDocket.lnk")
)
foreach ($l in $links) {
    if (Test-Path $l) { Remove-Item $l -Force }
}

if (Test-Path $dest) {
    Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "FileDocket is removed. Organized files were not deleted."
Write-Host "To also remove settings: rmdir /s %USERPROFILE%\.file-organizer"
Write-Host "(Skip that if that folder is your source checkout.)"
