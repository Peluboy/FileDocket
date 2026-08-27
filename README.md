# ⬇ FileDocket

**Your Downloads, Automatically Organized.**

A free, open-source macOS menu bar app that sorts your messy Downloads folder into neat categories, Images, Documents, Audio, Video, Code, and more.

```
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" && brew tap peluboy/tap && brew install --cask --no-quarantine filedocket
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

### Option 1: Homebrew (Recommended)

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
brew tap peluboy/tap
brew install --cask --no-quarantine filedocket
```

If you just installed Homebrew, either run the `export PATH=...` line above in the same window, or **open a new Terminal** so `brew` is on PATH. `brew: command not found` means the current session cannot see Homebrew yet. You can also skip Homebrew and use the DMG below.

### Option 2: Direct Download

1. Download the latest `.dmg` from [v1.2.0](https://github.com/Peluboy/homebrew-tap/raw/v1.2.0/FileDocket.dmg)
2. Open the `.dmg` and drag **FileDocket** to your Applications folder
3. Launch FileDocket from Applications

### First launch (Gatekeeper)

FileDocket is not notarized, so a double-click often shows *can't be opened* with no Open Anyway button. That is normal on current macOS.

**Fix (one-time), in this order:**

1. In **Finder → Applications**, Control-click **FileDocket** → **Open** → **Open**.
2. If the dialog only has **Done**, click Done, then **System Settings → Privacy & Security**, scroll to the bottom, and click **Open Anyway**. The button only appears after a blocked open.
3. If Open Anyway still never shows:

```bash
xattr -cr /Applications/FileDocket.app
```

Then Control-click → Open again.

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

FileDocket runs **entirely on your Mac**. No network requests, no analytics, no telemetry. Your files never leave your machine.

## Support

Email: imulep2104@gmail.com

## License

MIT © [Peluboy](https://github.com/peluboy)
