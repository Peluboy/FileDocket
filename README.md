# ⬇ FileDocket

**Your Downloads, Automatically Organized.**

A free, open-source macOS menu bar app that sorts your messy Downloads folder into neat categories, Images, Documents, Audio, Video, Code, and more.

```
curl -fsSL https://peluboy.github.io/FileDocket/install.sh | bash
```

---

## Features

| Feature | Free | Pro ($8) |
|---------|:----:|:--------:|
| Organize Downloads | ✅ | ✅ |
| Auto-Organize (background) | ✅ | ✅ |
| Undo & History | ✅ | ✅ |
| Custom Rules | 3 max | Unlimited |
| Extra Folders (beyond Downloads) | 1 | Unlimited |
| Duplicate Finder | ❌ | ✅ |
| Deep Scan (inside folders) | ❌ | ✅ |
| Archive Old Files (90d+) | ❌ | ✅ |

## Install

You do not need Homebrew.

**No Terminal:** [Download the DMG](https://github.com/Peluboy/homebrew-tap/raw/v1.2.2/FileDocket.dmg), drag FileDocket into Applications. If macOS blocks it, run `xattr -cr /Applications/FileDocket.app`.

**One command** (uses Homebrew if `brew` is present, otherwise the DMG, then clears quarantine):

```bash
curl -fsSL https://peluboy.github.io/FileDocket/install.sh | bash
```

**Homebrew only:**

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
brew install --cask peluboy/tap/filedocket
```

If you already ran `brew tap peluboy/filedocket`, the installer untaps it. To do that yourself: `brew untap peluboy/filedocket`.

macOS 12+, Intel and Apple Silicon.

### First launch (Gatekeeper)

FileDocket is not notarized. On macOS Sequoia and later, a double-click shows *Not Opened* with only **Done** and **Move to Trash**. That is normal. Control-click → Open no longer bypasses Gatekeeper.

**Fix (one-time):**

1. Open FileDocket once. Click **Done** (not Move to Trash).
2. **System Settings → Privacy & Security**, scroll to **Security**, click **Open Anyway**, then authenticate. The button only appears after a blocked open.
3. If Open Anyway never shows:

```bash
xattr -cr /Applications/FileDocket.app
```

Then open FileDocket again. Homebrew installs already strip quarantine, so this step is often unnecessary.

### Uninstall

```bash
curl -fsSL https://peluboy.github.io/FileDocket/uninstall.sh | bash
```

Or Homebrew:

```bash
brew uninstall --cask peluboy/tap/filedocket
```

To also remove settings and background agents:

```bash
brew uninstall --cask --zap peluboy/tap/filedocket
```

If you installed from the DMG: quit FileDocket from the menu bar, drag it from Applications to Trash, then run:

```bash
launchctl bootout "gui/$(id -u)/com.filedocket.organizer" 2>/dev/null
launchctl bootout "gui/$(id -u)/com.filedocket.login" 2>/dev/null
rm -f ~/Library/LaunchAgents/com.filedocket.organizer.plist ~/Library/LaunchAgents/com.filedocket.login.plist
```

`--zap` / deleting `~/.file-organizer` removes local settings. Organized files in Downloads stay where they are.

## How It Works

1. Click the ⬇ icon in your menu bar
2. Click **Organize Now**
3. Done, your files are sorted into neat categories

**Categories include:** Images, Documents, Audio, Video, Archives, Code, Fonts, Installers, and more.

## Auto-Organize

Enable **Auto-Organize in Background** from the menu to have your files sorted automatically whenever new downloads arrive. Uses macOS `launchd`, no background process running all the time.

## Custom Rules

Right-click the ⬇ icon → **Rules** → Add rules like:

- Files containing "invoice" → `Finance/`
- Files ending in `.iso` → `ISOs/`

## Undo

Every move is recorded. Click **Undo** to put any file back to its original location.

## Pro

Pro unlocks power tools for a one-time $8 payment:

- **Duplicate Finder**, Find and clean up duplicate files across your organized folders
- **Deep Scan**, Look inside organized folders for misplaced files
- **Unlimited Rules**, No cap on custom organization rules
- **Unlimited Folders**, Organize any number of folders, not just Downloads
- **Archive Old Files**, Automatically move old installers and archives

[Get Pro →](https://peluboy.lemonsqueezy.com)

## Building from Source

```bash
# Install dependencies
pip3 install rumps pyinstaller

# Run the app directly
python3 menu_bar.py

# Build the .app + DMG (universal: Intel + Apple Silicon)
./build_macos_release.sh
```

## Tech Stack

- **Python 3** + [rumps](https://github.com/jaredks/rumps) (macOS menu bar framework)
- **PyInstaller** for self-contained .app bundles
- **launchd** for background scheduling
- **AppKit** for native macOS UI elements

## Privacy

FileDocket runs **entirely on your Mac**. No network requests, no analytics, no telemetry. Your files never leave your machine.

## Support

Email: imulep2104@gmail.com

## License

MIT © [Peluboy](https://github.com/peluboy)
