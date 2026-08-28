# FileDocket Windows installer.
# Works on 64-bit Windows 10 and 11 (PowerShell 5.1 or 7, Command Prompt, Windows Terminal).
# Tries the Setup exe silently. If that fails (SmartScreen, blocked Inno), copies FileDocket.exe into %LOCALAPPDATA%.
#
# PowerShell:
#   irm https://peluboy.github.io/FileDocket/install.ps1 | iex
# Command Prompt:
#   powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://peluboy.github.io/FileDocket/install.ps1 | iex"

$ErrorActionPreference = "Stop"
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {}

if ($env:OS -ne "Windows_NT") {
    Write-Host "This installer is for Windows."
    Write-Host "macOS: curl -fsSL https://peluboy.github.io/FileDocket/install.sh | bash"
    return
}

$osVer = [Environment]::OSVersion.Version
if ($osVer.Major -lt 10) {
    Write-Host "FileDocket needs Windows 10 or later."
    return
}

if (-not [Environment]::Is64BitOperatingSystem) {
    Write-Host "FileDocket needs 64-bit Windows (x64 or ARM64 with x64 emulation)."
    return
}

$Release = "https://github.com/Peluboy/FileDocket/releases/download/windows-installer"
$SetupUrl = "$Release/FileDocket-Setup.exe"
$ExeUrl = "$Release/FileDocket.exe"
$CmdUrl = "$Release/organize.cmd"
$Dest = Join-Path $env:LOCALAPPDATA "FileDocket"
$ExePath = Join-Path $Dest "FileDocket.exe"

function Get-FdFile([string]$Url, [string]$OutFile) {
    $dir = Split-Path $OutFile -Parent
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -fsSL $Url -o $OutFile
        if (($LASTEXITCODE -eq 0) -and (Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) {
            return
        }
    }
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
    if (-not (Test-Path $OutFile) -or ((Get-Item $OutFile).Length -le 0)) {
        throw "Download failed: $Url"
    }
}

function Unblock-Fd([string]$Path) {
    if (Test-Path $Path) {
        Unblock-File -Path $Path -ErrorAction SilentlyContinue
    }
}

function Stop-FileDocket {
    Get-Process -Name "FileDocket" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

function New-FdShortcut([string]$LinkPath, [string]$Target) {
    $folder = Split-Path $LinkPath -Parent
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
    }
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($LinkPath)
    $s.TargetPath = $Target
    $s.WorkingDirectory = Split-Path $Target -Parent
    $s.Save()
}

function Install-Portable {
    Write-Host "Setup did not finish. Installing the portable exe instead..."
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    Stop-FileDocket
    Get-FdFile $ExeUrl $ExePath
    Get-FdFile $CmdUrl (Join-Path $Dest "organize.cmd")
    Unblock-Fd $ExePath
    New-FdShortcut (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\FileDocket.lnk") $ExePath
    New-FdShortcut (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\FileDocket.lnk") $ExePath
    $tr = "`"$Dest\organize.cmd`""
    & schtasks.exe /create /tn "FileDocket" /tr $tr /sc minute /mo 15 /f | Out-Null
}

Stop-FileDocket

$tmp = Join-Path $env:TEMP "FileDocket-Setup.exe"
Write-Host "Downloading FileDocket..."
Get-FdFile $SetupUrl $tmp
Unblock-Fd $tmp

Write-Host "Installing (silent, no admin)..."
$p = Start-Process -FilePath $tmp -ArgumentList "/VERYSILENT","/NORESTART","/SUPPRESSMSGBOXES","/CLOSEAPPLICATIONS","/TASKS=autostart,startup" -Wait -PassThru
$ok = (Test-Path $ExePath)

if (-not $ok) {
    try {
        Install-Portable
        $ok = (Test-Path $ExePath)
    } catch {
        Write-Host $_
        Write-Host "Could not install. Download FileDocket-Setup.exe from"
        Write-Host "https://github.com/Peluboy/FileDocket/releases/download/windows-installer/FileDocket-Setup.exe"
        Write-Host "If SmartScreen appears: More info, then Run anyway."
        return
    }
}

if (-not $ok) {
    Write-Host "Install finished, but FileDocket.exe is missing."
    return
}

Write-Host "FileDocket is in $Dest. Opening it now."
Start-Process $ExePath
Write-Host "Look for the FileDocket icon in the notification area (show hidden icons if needed)."
Write-Host "To update later, run this command again."
Write-Host "Uninstall: irm https://peluboy.github.io/FileDocket/uninstall.ps1 | iex"
