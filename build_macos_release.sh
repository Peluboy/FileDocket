#!/bin/bash
#
# build_macos_release.sh — For the DEVELOPER.
#
# Produces a single, easy-to-install DMG that a non-technical user can use with
# NO terminal and NO Python:  double-click the .dmg → drag FileFlow
# into Applications → done.
#
# The built .app is fully self-contained: the background "Auto-Organize"
# scheduler uses a CLI binary embedded *inside* the bundle, so the .app works by
# itself anywhere (no companion files needed).
#
# ══ What this script produces ═══════════════════════════════════════════════
#   dist/FileFlow.dmg     <- SHARE THIS with users (macOS)
#
# ══ Prerequisites (one-time, on YOUR machine, NOT the user's) ═══════════════
#   * Python 3 with PyInstaller and rumps installed:
#         python3 -m pip install pyinstaller rumps
#   * (Recommended for a truly seamless, no-warning install) a paid Apple
#     Developer account to sign + notarize. See DISTRIBUTION.md. Without this,
#     users still double-click the dmg, but Gatekeeper shows an
#     "unidentified developer" warning the first time.
#
# ══ Usage ═══════════════════════════════════════════════════════════════════
#   ./build_macos_release.sh              # builds .app + .dmg (ad-hoc sign)
#   ./build_macos_release.sh --notarize   # also codesign + notarize (needs your
#                                         #   Developer ID cert & notary profile)
#   TARGET_ARCH=universal2 ./build_macos_release.sh   # universal (Intel+ARM)
#
#   Overridables:
#     NOTARY_PROFILE     keychain profile name (default "AC_NOTARY")
#     SIGN_IDENTITY      codesign identity (default "Developer ID Application")
#============================================================================
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="FileFlow"
VOL_NAME="FileFlow"
DMG="FileFlow.dmg"
DMG_OUT="dist/$DMG"
TARGET_ARCH="${TARGET_ARCH:-arm64}"          # change to universal2 for Intel+ARM

DO_SIGN=0
[[ "${1:-}" == "--notarize" ]] && DO_SIGN=1

echo "▸ Building embedded CLI (one-file binary)…"
rm -f dist/fileflow-cli
python3 -m PyInstaller --onefile --name fileflow-cli --target-arch "$TARGET_ARCH" organize_downloads.py >/dev/null
test -f dist/fileflow-cli || { echo "❌ CLI build failed"; exit 1; }

echo "▸ Building the .app bundle (self-contained)…"
# Clean old build outputs so we never bake stale files in.
# Note: arch is inherited from the build machine for the .spec build.
rm -rf build dist/FileFlow.app FileFlow.app work
python3 -m PyInstaller --noconfirm --clean FileFlow.spec >/dev/null
APP="dist/FileFlow.app"
test -d "$APP" || { echo "❌ .app build failed"; exit 1; }

# Basic sanity: make sure the CLI actually made it inside the bundle.
if ! find "$APP" -name "fileflow-cli" | grep -q .; then
  echo "❌ embedded CLI not found inside the .app — auto-organize won't work."; exit 1
fi

if [[ "$DO_SIGN" == "1" ]]; then
  IDENTITY="${SIGN_IDENTITY:-Developer ID Application}"
  if ! security find-identity -v -p codesigning | grep -q "$IDENTITY"; then
    echo "❌ Developer ID certificate not found. See DISTRIBUTION.md."; exit 1
  fi
  echo "🔏 Code-signing the .app (hardened runtime + timestamp)…"
  codesign --force --options runtime --timestamp --sign "$IDENTITY" "$APP"
  codesign --verify --strict --verbose=2 "$APP"
fi

echo "▸ Packaging into a drag-to-Applications DMG…"
STAGE="$(mktemp -d)/$VOL_NAME"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
# A symlink to /Applications is what makes "drag here to install" work.
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG_OUT"
hdiutil create -volname "$VOL_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG_OUT" >/dev/null
rm -rf "$STAGE"

if [[ "$DO_SIGN" == "1" ]]; then
  NOTARY_PROFILE="${NOTARY_PROFILE:-AC_NOTARY}"
  echo "📤 Notarizing the DMG (may take a few minutes)…"
  xcrun notarytool submit "$DMG_OUT" --keychain-profile "$NOTARY_PROFILE" --wait
  echo "🖇  Stapling the notarization ticket…"
  xcrun stapler staple "$DMG_OUT"
  spctl -a -t open --context context:primary-signature -v "$DMG_OUT"
fi

echo ""
echo "✅ Done."
echo "   • Arch:          $TARGET_ARCH"
echo "   • .app bundle:   dist/FileFlow.app   (self-contained)"
echo "   • Installer:     $DMG_OUT   ← share THIS file."
echo ""
echo "   Users: double-click the dmg, drag 'FileFlow' onto"
echo "   'Applications', then launch it. No terminal, no Python on their side."