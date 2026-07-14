# Distribution & Signing Guide (for you, the developer)

This explains how to hand the Downloads Organizer to other people cleanly. It's separate from
`README.md`, which is written for the *end users* who receive it.

## The core problem: Gatekeeper

macOS Gatekeeper blocks apps from "unidentified developers." What a recipient sees depends on
how the binary is signed:

| State | What the recipient experiences |
|---|---|
| **Ad-hoc signed** (current) | Scary "cannot be opened / unidentified developer" block. They must right-click ▸ Open, or strip quarantine manually. |
| **Signed + notarized** (goal) | Opens normally, no warning. This is what "signing" buys you. |

Ad-hoc signing (what PyInstaller already did) only lets the binary *run locally*. It does **not**
help anyone who downloads it.

---

## Option A — Free path (no Apple account)

You can distribute the ad-hoc binary as-is; recipients just need one of these the first time:

- **Right-click the file ▸ Open ▸ Open** (the README already walks users through this), or
- Strip the quarantine flag before running:
  ```bash
  xattr -d com.apple.quarantine DownloadsOrganizer-Mac
  ```

This is fine for friends/colleagues. It is not appropriate for wide/public distribution.

---

## Option B — Proper path (signed + notarized) ← recommended for real distribution

### Prerequisites (one-time)
1. **Apple Developer Program** membership — $99/yr: <https://developer.apple.com/programs/>
2. A **Developer ID Application** certificate in your keychain
   (Xcode ▸ Settings ▸ Accounts ▸ Manage Certificates ▸ + ▸ *Developer ID Application*).
   Verify: `security find-identity -v -p codesigning`
3. An **app-specific password**: <https://account.apple.com> ▸ Sign-In & Security.
4. Save notarization credentials once:
   ```bash
   xcrun notarytool store-credentials "AC_NOTARY" \
     --apple-id "you@example.com" --team-id "YOURTEAMID" --password "abcd-efgh-ijkl-mnop"
   ```

### Then, every time you ship a new build
```bash
./sign_and_notarize_mac.sh
```
That signs the binary (hardened runtime + timestamp), submits it to Apple, and waits for the
"Accepted" result.

### Stapling / offline approval
A **bare binary can't be stapled** (stapling attaches the notarization ticket to a container).
Notarization still works — Gatekeeper verifies online on first launch. For offline-proof approval
(and a nicer install), wrap the binary in a container and staple that:

- **.dmg**: `hdiutil create -volname "Downloads Organizer" -srcfolder <folder> -ov -format UDZO DownloadsOrganizer.dmg`
  then `codesign` + notarize + `xcrun stapler staple DownloadsOrganizer.dmg`
- **.pkg** (installer that can also set up the background agent): `pkgbuild` / `productbuild`,
  then notarize + `xcrun stapler staple`.

Ask and I can build either wrapper + wire it into `sign_and_notarize_mac.sh`.

---

## Architecture note (Intel vs Apple Silicon)
The current binary is **arm64 only** — it won't run on Intel Macs. To cover both, build a
**universal2** binary (needs a universal Python + PyInstaller `--target-arch universal2`), or
ship separate arm64/x86_64 builds. Say the word and I'll set that up.
