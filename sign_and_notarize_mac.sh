#!/bin/bash
#
# Sign + notarize the macOS binary so people can open it without Gatekeeper warnings.
#
# ── ONE-TIME SETUP (requires a paid Apple Developer account, $99/yr) ─────────────
#
#   1. Enroll: https://developer.apple.com/programs/
#
#   2. Create a "Developer ID Application" certificate and install it in your login
#      keychain — easiest via Xcode ▸ Settings ▸ Accounts ▸ (your account) ▸
#      Manage Certificates ▸ + ▸ "Developer ID Application".
#      Confirm it's there:   security find-identity -v -p codesigning
#
#   3. Make an app-specific password for notarization:
#      https://account.apple.com ▸ Sign-In & Security ▸ App-Specific Passwords
#
#   4. Save your notarization credentials once (notarytool reuses them by name):
#        xcrun notarytool store-credentials "AC_NOTARY" \
#          --apple-id "you@example.com" \
#          --team-id  "YOURTEAMID" \
#          --password "abcd-efgh-ijkl-mnop"
#
# ── USAGE ────────────────────────────────────────────────────────────────────────
#   ./sign_and_notarize_mac.sh
#
#   Optional overrides:
#     SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"  # exact identity
#     NOTARY_PROFILE="AC_NOTARY"                                    # keychain profile name
#
set -euo pipefail
cd "$(dirname "$0")"

BINARY="FileFlow-Mac"
IDENTITY="${SIGN_IDENTITY:-Developer ID Application}"
NOTARY_PROFILE="${NOTARY_PROFILE:-AC_NOTARY}"

[ -f "$BINARY" ] || { echo "❌ $BINARY not found here. Build it first."; exit 1; }

# Fail early with a clear message if there's no Developer ID cert.
if ! security find-identity -v -p codesigning | grep -q "Developer ID Application"; then
  echo "❌ No 'Developer ID Application' certificate found in your keychain."
  echo "   See the ONE-TIME SETUP notes at the top of this script."
  exit 1
fi

echo "🔏 Signing '$BINARY' with hardened runtime + secure timestamp…"
codesign --force --options runtime --timestamp --sign "$IDENTITY" "$BINARY"
codesign --verify --strict --verbose=2 "$BINARY"
echo "   ✓ signature valid"

echo "🗜  Packaging for notarization…"
ZIP="FileFlow-Mac-notarize.zip"
rm -f "$ZIP"
/usr/bin/ditto -c -k --keepParent "$BINARY" "$ZIP"

echo "📤 Submitting to Apple's notary service (waits for the result — can take a few min)…"
xcrun notarytool submit "$ZIP" --keychain-profile "$NOTARY_PROFILE" --wait

# NOTE: a *bare* Mach-O binary cannot be "stapled" (stapling works on .app/.dmg/.pkg).
# Notarization still registers the binary's hash with Apple, so Gatekeeper approves it
# on first run **while online**. For offline-proof approval, ship it wrapped in a
# notarized+stapled .dmg or .app (see DISTRIBUTION.md).
echo ""
echo "✅ Done."
echo "   • Signed binary:      $BINARY"
echo "   • Notarized bundle:   $ZIP  (distribute this, or the signed binary)"
echo "   • Sanity check:       codesign -dvvv $BINARY   |   spctl -a -t exec -vv $BINARY"
