#!/usr/bin/env bash
# FileDocket uninstall: brew if it was a cask install, otherwise remove the app.
# Does not delete ~/.file-organizer (settings, or a local git clone).
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This uninstall script is for macOS."
  echo "Windows PowerShell: irm https://peluboy.github.io/FileDocket/uninstall.ps1 | iex"
  echo "Or Settings → Apps → FileDocket."
  exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
APP="/Applications/FileDocket.app"
UID_NUM="$(id -u)"

osascript -e 'quit app "FileDocket"' >/dev/null 2>&1 || true
sleep 1

if command -v brew >/dev/null 2>&1 && brew list --cask filedocket >/dev/null 2>&1; then
  brew uninstall --cask peluboy/tap/filedocket
else
  rm -rf "$APP"
fi

launchctl bootout "gui/${UID_NUM}/com.filedocket.organizer" >/dev/null 2>&1 || true
launchctl bootout "gui/${UID_NUM}/com.filedocket.login" >/dev/null 2>&1 || true
rm -f "$HOME/Library/LaunchAgents/com.filedocket.organizer.plist" \
      "$HOME/Library/LaunchAgents/com.filedocket.login.plist"

echo "FileDocket is removed. Organized files in Downloads were not deleted."
echo "To also remove settings: rm -rf ~/.file-organizer"
echo "(Skip that if ~/.file-organizer is your source checkout.)"
