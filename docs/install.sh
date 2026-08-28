#!/usr/bin/env bash
# FileDocket installer: uses Homebrew when present, otherwise the DMG.
# Always clears Gatekeeper quarantine so first launch does not depend on Settings.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS."
  echo "Windows PowerShell: irm https://peluboy.github.io/FileDocket/install.ps1 | iex"
  echo "Windows Command Prompt: powershell -NoProfile -ExecutionPolicy Bypass -Command \"irm https://peluboy.github.io/FileDocket/install.ps1 | iex\""
  exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
APP="/Applications/FileDocket.app"
DMG_URL="https://github.com/Peluboy/homebrew-tap/raw/main/FileDocket.dmg"

quit_app() {
  osascript -e 'quit app "FileDocket"' >/dev/null 2>&1 || true
  sleep 1
}

clear_quarantine() {
  if [[ -d "$APP" ]]; then
    xattr -cr "$APP" >/dev/null 2>&1 || true
  fi
}

install_from_dmg() {
  echo "Homebrew not found. Installing from the DMG…"
  local tmp mnt
  tmp="$(mktemp -d)"
  mnt="$(mktemp -d)"
  curl -fsSL -o "$tmp/FileDocket.dmg" "$DMG_URL"
  hdiutil attach -nobrowse -quiet -mountpoint "$mnt" "$tmp/FileDocket.dmg"
  if [[ ! -d "$mnt/FileDocket.app" ]]; then
    hdiutil detach "$mnt" -quiet || true
    echo "The DMG did not contain FileDocket.app."
    exit 1
  fi
  quit_app
  rm -rf "$APP"
  ditto "$mnt/FileDocket.app" "$APP"
  hdiutil detach "$mnt" -quiet
  rm -rf "$tmp" "$mnt"
}

if command -v brew >/dev/null 2>&1; then
  echo "Homebrew found. Installing with brew…"
  brew untap peluboy/filedocket >/dev/null 2>&1 || true
  quit_app
  brew install --cask --force peluboy/tap/filedocket
else
  install_from_dmg
fi

clear_quarantine

if [[ ! -d "$APP" ]]; then
  echo "Install finished, but $APP is missing."
  exit 1
fi

echo "FileDocket is in Applications. Opening it now."
open -a FileDocket || true
echo "Look for the FileDocket icon in the menu bar."
