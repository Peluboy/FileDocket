# ⬇ FileFlow

**Your Downloads, Automatically Organized.**

A free, open-source macOS menu bar app that sorts your messy Downloads folder into neat categories, Images, Documents, Audio, Video, Code, and more.

```
brew tap peluboy/fileflow && brew install --cask fileflow
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
| Duplicate Finder |, | ✅ |
| Deep Scan (inside folders) |, | ✅ |
| Archive Old Files (90d+) |, | ✅ |

## Install

### Option 1: Homebrew (Recommended)

```bash
brew tap peluboy/fileflow
brew install --cask fileflow
```

### Option 2: Direct Download

1. Download the latest `.dmg` from [Releases](https://github.com/peluboy/FileFlow/releases/latest)
2. Open the `.dmg` and drag **FileFlow** to your Applications folder
3. Launch FileFlow from Applications

### ⚠️ Gatekeeper Warning

Since FileFlow isn't on the Mac App Store, macOS may show a warning:

> *"FileFlow can't be opened because Apple cannot check it for malicious software."*

**Fix (one-time):** Right-click the app → **Open** → Click **Open** in the dialog.

Alternatively: **System Settings → Privacy & Security → scroll down → click "Open Anyway"** next to FileFlow.

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

[Get Pro →](https://your-landing-page.com/#pricing)

## Building from Source

```bash
# Install dependencies
pip3 install rumps pyinstaller

# Run the app directly
python3 menu_bar.py

# Build the .app bundle
./build_macos_release.sh

# Build universal (Intel + ARM)
TARGET_ARCH=universal2 ./build_macos_release.sh
```

## Tech Stack

- **Python 3** + [rumps](https://github.com/jaredks/rumps) (macOS menu bar framework)
- **PyInstaller** for self-contained .app bundles
- **launchd** for background scheduling
- **AppKit** for native macOS UI elements

## Privacy

FileFlow runs **entirely on your Mac**. No network requests, no analytics, no telemetry. Your files never leave your machine.

## License

MIT © [Peluboy](https://github.com/peluboy)
