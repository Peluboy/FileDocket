# Downloads Organizer

Automatically tidies your **Downloads** folder by sorting loose files into neat, categorized
folders — Images, Documents, Videos, Audio, Archives, Installers, Code, Design, Fonts, Other.

**It's safe.** It only ever moves loose files sitting *directly* in your Downloads folder.
It never deletes anything, never touches folders you've already made, and never moves a file
that's still downloading.

---

## 🍎 macOS

### The easy way: Menu Bar App
1. **Right-click** `DownloadsOrganizer.app` → **Open**. *(Right-click the first time — not double-click.)*
2. If macOS warns it's from an **"unidentified developer,"** click **Open** to confirm.
3. A small download icon (📥) will appear in your top menu bar!
4. Click the icon to:
   - Run a manual clean up (**Organize Now**)
   - Toggle background sorting (**Auto-Organize in Background**)
   - View recent logs or status updates

> #### ⚠️ "Operation not permitted" or background sorting not working?
> macOS has strict security rules for background programs:
> 1. Open **System Settings → Privacy & Security → Full Disk Access**
> 2. Click **+**, and add **`DownloadsOrganizer-Mac`** (located in this folder)
> 3. Make sure its switch is turned **ON**
> 
> *Note: When the menu-bar app runs for the first time, macOS will show a standard prompt asking to access your Downloads folder. Just click **OK**.*

> 💡 **This build runs on Apple Silicon Macs** (M1/M2/M3 and newer). Intel Mac support needs a
> universal build.

---

## 🪟 Windows

### Run it once
Double-click **`run.bat`**.
*(If it says `DownloadsOrganizer.exe` is missing, double-click `build_windows_exe.bat` once to create it.)*

### Run it automatically
Double-click **`install_win_auto.bat`** — it sorts your Downloads every 15 minutes in the background.
To stop: double-click **`uninstall_win_auto.bat`**.

---

## Where your files go

| Folder | Examples |
|---|---|
| **Images** | png, jpg, gif, svg, heic, webp, tiff |
| **Documents** | pdf, docx, txt, xlsx, pptx, csv, epub |
| **Videos** | mp4, mov, mkv, webm, avi |
| **Audio** | mp3, wav, m4a, flac, aac |
| **Archives** | zip, rar, 7z, tar, iso |
| **Installers** | dmg, pkg, exe, msi |
| **Design** | psd, ai, indd, eps, fig, sketch |
| **Code** | html, js, py, json, css, xml |
| **Fonts** | ttf, otf, woff, woff2 |
| **Other** | anything that doesn't fit above |

---

**Is anything ever lost?** No. The organizer only *moves* files into folders — it never deletes.
If you don't like where something landed, it's right there in its category folder to move back.
