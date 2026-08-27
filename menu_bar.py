import os
import sys
import time
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
import rumps
import organize_downloads
import license as license_mod

APP_NAME = "FileFlow"
APP_VERSION = "1.2.0"
APP_AUTHOR = "Peluboy"

# Icon paths for menu items
def _icon(name):
    """Return the path to an icon resource, or None if not found."""
    p = resource_path(os.path.join("icons", f"{name}.png"))
    if os.path.isfile(p):
        return p
    return None

def _set_menu_icon(menu_item, icon_name):
    """Set a template icon on a menu item so it adapts to dark/light mode."""
    path = _icon(icon_name)
    if not path:
        return
    try:
        from AppKit import NSImage as _NSImage
        img = _NSImage.alloc().initWithContentsOfFile_(path)
        if img:
            img.setTemplate_(True)  # auto white/dark based on menu background
            # Try the direct NSMenuItem setter first
            if hasattr(menu_item, '_menuitem') and menu_item._menuitem is not None:
                menu_item._menuitem.setImage_(img)
            else:
                # Fallback: rumps icon setter
                menu_item.icon = path
    except Exception:
        menu_item.icon = path

# Text shown in the menu bar while the app is working.
# Use a simple ASCII-visible character so it's obvious the app is busy.
BUSY_BUSY_TEXT = "Working…"

# Define Paths
LOG_DIR = Path.home() / ".file-organizer"
LOG_FILE = LOG_DIR / "activity.log"
STATE_FILE = LOG_DIR / "last_run.json"
SETTINGS_FILE = LOG_DIR / "settings.json"
HISTORY_FILE = LOG_DIR / "history.json"
PLIST_PATH = Path.home() / "Library/LaunchAgents/com.fileflow.organizer.plist"
LOGIN_PLIST = Path.home() / "Library/LaunchAgents/com.fileflow.login.plist"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class FileFlowApp(rumps.App):
    def __init__(self):
        try:
            with open("/tmp/menu_bar_debug.log", "a") as f:
                f.write("FileFlowApp __init__ started\n")
        except Exception as e:
            pass
        super(FileFlowApp, self).__init__("FileFlow", icon=resource_path("status_iconTemplate.png"), template=True,
                                          quit_button=None)
        
        # Initialize menu items
        self.last_run_item = rumps.MenuItem("Last Run: Checking...", callback=None)
        self.organize_now_item = rumps.MenuItem("Organize Now", callback=self.organize_now)
        self.toggle_auto_item = rumps.MenuItem("Auto-Organize in Background", callback=self.toggle_auto)
        self.undo_last_item = rumps.MenuItem("↩ Undo Last Move", callback=self.undo_last)
        self.undo_history_item = rumps.MenuItem("Undo History")
        self.folders_item = rumps.MenuItem("Add Folders")
        self.rules_item = rumps.MenuItem("Rules")
        self.tools_item = rumps.MenuItem("Tools")
        self.launch_login_item = rumps.MenuItem("Launch FileFlow at login", callback=self.toggle_launch_login)
        self.welcome_item = rumps.MenuItem("Welcome Guide", callback=self.show_welcome)
        self.about_item = rumps.MenuItem("About FileFlow", callback=self.show_about)
        self.support_item = rumps.MenuItem("Support", callback=self.show_support)
        self.get_pro_item = rumps.MenuItem("Pro", callback=self.show_get_pro)
        _set_menu_icon(self.get_pro_item, "icon-pro-crown")
        self.quit_item = rumps.MenuItem("Quit FileFlow", key="q", callback=self.quit_app)
        self.view_log_item = rumps.MenuItem("View Activity Log", callback=self.view_log)
        
        # Build menu
        self.menu = [
            self.last_run_item,
            rumps.separator,
            self.organize_now_item,
            self.toggle_auto_item,
            self.undo_last_item,
            self.undo_history_item,
            self.tools_item,
            self.folders_item,
            self.rules_item,
            rumps.separator,
            self.launch_login_item,
            self.view_log_item,
            self.get_pro_item,
            rumps.separator,
            self.welcome_item,
            self.about_item,
            self.support_item,
            rumps.separator,
            self.quit_item,
        ]

        # Busy/animation state for the tray icon (spinner while working)
        self._busy = 0
        self._anim_timer = None
        self._anim_index = 0
        self._icon_frames = None
        self._base_icon = resource_path("status_iconTemplate.png")
        # Build the animation frames up-front so the first busy action starts
        # spinning instantly instead of paying the draw cost mid-click.
        try:
            self._busy_frames()
        except Exception:
            pass
        
        # Set initial auto-organize check state
        self.update_auto_state()
        self.update_launch_login_state()
        
        # Load initial last run state
        self.update_last_run_ui()

        # Populate foldable submenus (rules, undo history, extra folders)
        self.refresh_undo_menu()
        self.refresh_folders_menu()
        self.refresh_rules_menu()
        self._build_tools_menu()

        # Greet the user / point them to the menu-bar icon
        self._startup_greeting()

        # Start a periodic timer to update the last run time text (every 30 seconds)
        self.timer = rumps.Timer(self.periodic_update, 30)
        self.timer.start()

        # ---- Main-thread UI queue ---------------------------------------
        # Background threads compute results (find_duplicates, classify_by_category,
        # the CLI subprocess, etc.) but every GUI mutation MUST happen on the main
        # thread.  Posting rumps.Timer / rumps.alert / rumps.notification from a
        # worker thread produces NSTimers bound to the wrong runloop and silently
        # fails — which is why results/alerts sometimes never appeared.
        self._ui_q, self._ui_lock = [], threading.Lock()
        self._drain = rumps.Timer(self._drain_ui_queue, 0.7)
        self._drain.start()

        try:
            with open("/tmp/menu_bar_debug.log", "a") as f:
                f.write("FileFlowApp __init__ completed successfully\n")
        except Exception as e:
            pass

    def get_bin_path(self):
        """Return the CLI used by the background scheduler (Auto-Organize).

        Search order (so the app is fully self-contained when installed as a
        plain .app in /Applications):

          1. The `fileflow-cli` binary embedded as a resource inside
             this very bundle (new, self-contained layout).
          2. A companion CLI named `FileFlow-Mac` sitting *next to*
             this .app (legacy folder layout, kept for compatibility).
          3. The python source script (development mode).
        """
        # 1) Embedded CLI resource inside this PyInstaller bundle.
        #    On macOS .app bundles, PyInstaller's sys._MEIPASS points at
        #    Contents/Frameworks, and it also creates a Resources symlink. Check
        #    several candidate spots so it works however the layout is laid out.
        candidates = []
        try:
            candidates.append(resource_path("fileflow-cli"))
        except Exception:
            pass
        if getattr(sys, 'frozen', False):
            bundle_root = Path(sys.executable).parent.parent.parent  # == .app/Contents
            candidates += [
                bundle_root / "Frameworks" / "fileflow-cli",
                bundle_root / "Resources" / "fileflow-cli",
            ]
        for cand in candidates:
            if os.path.isfile(str(cand)):
                return Path(cand)

        # 2) Legacy companion binary next to FileFlow.app
        if getattr(sys, 'frozen', False):
            # sys.executable is inside FileFlow.app/Contents/MacOS/
            app_dir = Path(sys.executable).parent.parent.parent.parent
            bin_path = app_dir / "FileFlow-Mac"
            if bin_path.exists():
                return bin_path

        # 3) Development fallback: run the python source directly
        dev_script = Path(__file__).parent / "organize_downloads.py"
        if dev_script.exists():
            return dev_script
        return None

    def update_auto_state(self):
        """Checks launchd plist to set menu item checkbox state."""
        self.toggle_auto_item.state = 1 if PLIST_PATH.exists() else 0

    def get_extra_roots(self):
        """User-selected extra folders (beyond Downloads)."""
        return organize_downloads.load_extra_roots()

    def _pick_folder(self):
        """Let the user choose an extra folder (native picker, text fallback)."""
        try:
            from AppKit import NSOpenPanel
            panel = NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(False)
            panel.setCanChooseDirectories_(True)
            panel.setAllowsMultipleSelection_(False)
            panel.setPrompt_("Choose Folder")
            if panel.runModal() and panel.URLs():
                return Path(panel.URLs()[0].path())
        except Exception:
            pass
        # Fallback: ask for a path as text (works even without AppKit).
        w = rumps.Window("Type the folder path to organize",
                         "Example: ~/Desktop", "", dimensions=(420, 40))
        resp = w.run()
        if resp.clicked and resp.text.strip():
            p = Path(resp.text.strip()).expanduser()
            if p.is_dir():
                return p
            rumps.alert(title="Folder not found", message=f"Couldn't find:\n{p}")
        return None

    def refresh_folders_menu(self):
        """Rebuild the 'Add Folders' submenu from current settings."""
        self._safe_clear(self.folders_item)
        downloads = Path.home() / "Downloads"
        self.folders_item.add(
            rumps.MenuItem(f"✓ {downloads}  (always)")
        )
        extras = self.get_extra_roots()
        if extras:
            self.folders_item.add(rumps.separator)
            for p in extras:
                item = rumps.MenuItem(f"✕ {p}")
                item.set_callback(lambda _, path=p: self.remove_extra_folder(path))
                self.folders_item.add(item)
        self.folders_item.add(rumps.separator)
        add_item = rumps.MenuItem("+ Add a folder…", callback=self.add_extra_folder)
        self.folders_item.add(add_item)
        # TITLE text is a plain string first arg; keep a count tooltip-style.
        self.folders_item.title = f"Add Folders ({len(extras)})"

    def add_extra_folder(self, sender=None):
        folder = self._pick_folder()
        if not folder:
            return
        existing = self.get_extra_roots()
        if folder in existing or folder == Path.home() / "Downloads":
            rumps.alert(title="Already added", message=f"{folder} is already being organized.")
            return
        # Free users limited to 1 extra folder
        if not license_mod.is_pro() and len(existing) >= 1:
            self._require_pro("Unlimited Extra Folders")
            return
        existing.append(folder)
        organize_downloads.save_extra_roots(existing)
        self.refresh_folders_menu()
        self._reload_plist_if_enabled()
        rumps.notification("FileFlow", "Folder added",
                           f"Now organizing: {folder}")

    def remove_extra_folder(self, path):
        existing = self.get_extra_roots()
        if path in existing:
            existing.remove(path)
            organize_downloads.save_extra_roots(existing)
            self.refresh_folders_menu()
            self._reload_plist_if_enabled()
            rumps.notification("FileFlow", "Folder removed",
                               f"No longer organizing: {path}")

    def _watch_paths(self):
        """Folders launchd should watch (Downloads + any extras)."""
        paths = [str(Path.home() / "Downloads")]
        for p in self.get_extra_roots():
            paths.append(str(p))
        return paths

    def _safe_clear(self, item):
        """Clear a submenu, tolerating childless submenus.

        A rumps submenu MenuItem only creates its underlying NSMenu once you add a
        child. Calling .clear() on a freshly-created (childless) submenu crashes in
        rumps, so we skip it when there is no underlying menu yet (nothing to clear).
        """
        try:
            if item._menu is not None:
                item.clear()
        except AttributeError:
            pass

    def refresh_undo_menu(self):
        """Rebuild the 'Undo History' submenu from recorded moves."""
        self._safe_clear(self.undo_history_item)
        entries = organize_downloads.load_history()
        if not entries:
            self.undo_history_item.add(
                rumps.MenuItem("No moves to undo yet", callback=None)
            )
            return
        for entry in reversed(entries[-20:]):  # show most recent 20
            name = entry.get("orig", "?")
            dest = Path(entry.get("dest", "")).parent.name or "…"
            item = rumps.MenuItem(f"↩ {name}  (from {dest})")
            item.set_callback(lambda _, e=entry: self.undo_specific(e))
            self.undo_history_item.add(item)
        self.undo_history_item.add(rumps.separator)
        clear = rumps.MenuItem("Clear history", callback=self.clear_history)
        self.undo_history_item.add(clear)

    def undo_last(self, sender=None):
        entry = organize_downloads.undo_last()
        self.after_undo(entry)

    def undo_specific(self, entry):
        ok = organize_downloads.undo_entry(entry)
        self.after_undo(entry if ok else None)

    def after_undo(self, entry):
        self.refresh_undo_menu()
        self.update_last_run_ui()
        if entry:
            rumps.notification("FileFlow", "Move undone",
                               f"Put back: {entry.get('orig')}")
        else:
            rumps.alert(title="Undo", message="Nothing to undo, or the file was "
                                              "already moved/deleted.")

    def clear_history(self, sender=None):
        try:
            HISTORY_FILE.write_text("[]\n")
        except Exception:
            pass
        self.refresh_undo_menu()

    def update_last_run_ui(self):
        """Reads state file and updates 'Last Run' text in menu."""
        if not STATE_FILE.exists():
            self.last_run_item.title = "Last Run: Never"
            return

        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            
            ts = data.get("timestamp")
            moved = data.get("moved", 0)
            
            if ts:
                dt = datetime.fromtimestamp(ts)
                diff = time.time() - ts
                
                # Format time string nicely
                if diff < 60:
                    time_str = "just now"
                elif diff < 3600:
                    time_str = f"{int(diff // 60)}m ago"
                elif diff < 86400:
                    time_str = f"{int(diff // 3600)}h ago"
                else:
                    time_str = dt.strftime("%b %d")
                
                self.last_run_item.title = f"Last Run: {time_str} ({moved} moved)"
            else:
                self.last_run_item.title = "Last Run: Never"
        except Exception as e:
            self.last_run_item.title = "Last Run: Error reading state"

    def periodic_update(self, sender):
        self.update_last_run_ui()
        self.update_auto_state()
        self.update_launch_login_state()
        self.refresh_undo_menu()
        self.refresh_folders_menu()
        self.refresh_rules_menu()

    def organize_now(self, sender):
        """Trigger file organizer in a separate thread so the UI does not freeze."""
        self._start_busy("Organizing…")
        threading.Thread(target=self.run_organization_thread).start()

    def run_organization_thread(self):
        """Worker thread: run the sorter and report the result on the main thread."""
        summary = {"message": "Nothing to organize."}
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            from contextlib import redirect_stdout, redirect_stderr
            with open(LOG_FILE, "a") as log:
                log.write(f"\n--- Menu-Bar Triggered Run: "
                          f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                with redirect_stdout(log), redirect_stderr(log):
                    # main() reads extra folders from settings.json for us.
                    organize_downloads.main([])
                    summary = self._build_summary()
        except Exception as e:
            try:
                with open(LOG_FILE, "a") as log:
                    log.write(f"Error during organization run: {e}\n")
            except Exception:
                pass
            summary = self._build_summary()

        # Every GUI update must happen on the main thread.  Posting rumps
        # notifications/timers from a worker thread produces NSTimers bound to
        # the wrong runloop and silently fails — that is why the "All tidy"
        # notification sometimes never appeared.  Route through the UI queue.
        note = summary.get("title", "Finished sorting")
        msg = summary.get("message", "...")

        def finalize():
            self._debug(f"finalize: notifying '{note}' / '{msg}'")
            self.notify(note, msg)
            self.organize_now_item.title = "Organize Now"
            self.organize_now_item.set_callback(self.organize_now)
            self.update_last_run_ui()
            self.refresh_undo_menu()
            self.refresh_folders_menu()
            self._stop_busy()

        self._debug(f"run_organization_thread: posting finalize (note={note!r})")
        self._post_ui(finalize)


    def _build_summary(self):
        """Build a friendly notification summary from the last run's stats."""
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            return {"title": "Finished sorting", "message": "Done, no changes."}
        moved = data.get("moved", 0)
        by_cat = data.get("by_cat", {}) or {}
        if moved <= 0:
            return {"title": "All tidy", "message": "No loose files to organize."}
        parts = ", ".join(f"{cat} {n}" for cat, n in
                          sorted(by_cat.items(), key=lambda kv: -kv[1])[:4])
        details = f"{moved} file{'s' if moved != 1 else ''} → {parts}"
        return {"title": f"Organized {moved} file{'s' if moved != 1 else ''}",
                "message": details}

    def toggle_auto(self, sender):
        """Enables or disables launchd auto-organization plist."""
        bin_path = self.get_bin_path()
        if not bin_path:
            rumps.alert(title="Error", message="Could not find executable binary to schedule background task.")
            return

        if PLIST_PATH.exists():
            try:
                self._disable_job()
                rumps.notification("FileFlow", "Auto-Organize Disabled", "Background service stopped.")
            except Exception as e:
                rumps.alert(title="Error", message=f"Failed to disable auto-organize: {e}")
        else:
            try:
                self._enable_job(bin_path)
                rumps.notification("FileFlow", "Auto-Organize Enabled", "Your folders will now be organized automatically.")
            except Exception as e:
                rumps.alert(title="Error", message=f"Failed to enable auto-organize: {e}")
                if PLIST_PATH.exists():
                    PLIST_PATH.unlink()

        self.update_auto_state()

    def _enable_job(self, bin_path):
        """Write + load the launchd job for the current set of folders."""
        if bin_path.suffix == ".py":
            args = ["/usr/bin/python3", str(bin_path.resolve())]
        else:
            args = [str(bin_path.resolve())]

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.fileflow.organizer</string>
    <key>ProgramArguments</key>
    <array>
        {"".join(f"<string>{arg}</string>" for arg in args)}
    </array>
    <key>WatchPaths</key>
    <array>
        {"".join(f"<string>{sp}</string>" for sp in self._watch_paths())}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>{LOG_FILE}</string>
</dict>
</plist>"""

        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLIST_PATH.write_text(plist_content)
        subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True)

    def _disable_job(self):
        """Unload + remove the launchd job."""
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        try:
            PLIST_PATH.unlink()
        except FileNotFoundError:
            pass

    def _reload_plist_if_enabled(self):
        """If Auto-Organize is on, refresh watch paths after a folder change."""
        if not PLIST_PATH.exists():
            return
        bin_path = self.get_bin_path()
        if not bin_path:
            return
        try:
            self._disable_job()
            self._enable_job(bin_path)   # no notifications here
        except Exception:
            pass

    # ---- Tray icon animation -----------------------------------------------

    def _debug(self, msg):
        """Append to the debug log instead of failing silently."""
        try:
            with open("/tmp/menu_bar_debug.log", "a") as f:
                f.write(f"{msg}\n")
        except Exception:
            pass

    def _once(self, seconds, fn):
        """Run `fn` on the main UI thread after `seconds`, exactly ONCE.

        rumps.Timer repeats until stopped, so every one-shot callback in this
        app must go through here instead of a bare rumps.Timer(...).start().
        """
        def tick(t=None):
            try:
                if t is not None:
                    t.stop()
            except Exception:
                pass
            fn()
        rumps.Timer(tick, max(0.05, seconds)).start()

    def _post_ui(self, fn):
        """Schedule a GUI update on the main thread from any worker thread.

        Background threads (organize worker, CLI subprocess caller, file
        classifier) push closures here; a repeating main-thread timer drains
        them, so no NSTimer is ever created off the main thread.
        """
        with self._ui_lock:
            self._ui_q.append(fn)

    def _drain_ui_queue(self, timer=None):
        """Main-thread drain for _post_ui callbacks."""
        with self._ui_lock:
            jobs, self._ui_q = list(self._ui_q), []
        for fn in jobs:
            try:
                fn()
            except Exception as e:
                self._debug(f"ui queue job failed: {e}")


    def notify(self, title, message):
        """User-visible notification with a visible failure path.

        If the macOS Notification Center silently swallows the alert (missing
        permission, sandbox restriction, etc.) we fall back to a modal dialog
        so the user always gets feedback.
        """
        self._debug(f"notify: {title!r} / {message!r}")
        try:
            rumps.notification(APP_NAME, str(title), str(message))
        except Exception as e:
            self._debug(f"notification failed ({title!r}): {e}")
            # Fallback: modal alert so the user always sees the result.
            try:
                rumps.alert(title=str(title), message=str(message))
            except Exception:
                pass

    def _draw_spinner(self, angle):
        """Draw one spinner frame (download arrow + rotating arc) as an NSImage."""
        from AppKit import NSImage, NSBezierPath, NSColor
        img = NSImage.alloc().initWithSize_((18, 18))
        img.lockFocus()
        try:
            p = NSBezierPath.bezierPath()
            p.setLineWidth_(1.6)
            p.moveToPoint_((9, 13)); p.lineToPoint_((9, 7.5))
            p.moveToPoint_((5.8, 10.0)); p.lineToPoint_((9, 6.6)); p.lineToPoint_((12.2, 10.0))
            p.moveToPoint_((5.5, 4.2)); p.lineToPoint_((12.5, 4.2))
            NSColor.blackColor().setStroke()
            p.stroke()
            if angle is not None:
                arc = NSBezierPath.bezierPath()
                arc.setLineWidth_(1.8)
                arc.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
                    (9, 9), 8.0, angle, angle + 100, False)
                arc.stroke()
        finally:
            img.unlockFocus()
        try:
            img.setTemplate_(True)
        except Exception:
            pass
        return img

    def _busy_frames(self):
        """Write spinner frames to temp files ONCE and cache their paths.

        rumps' icon setter only accepts file *paths* — passing NSImage objects
        fails silently, which is why the animation previously never appeared.
        """
        if self._icon_frames:
            return self._icon_frames
        try:
            from AppKit import NSBitmapImageRep
            frames_dir = Path("/tmp/fileflow-spinner")
            frames_dir.mkdir(parents=True, exist_ok=True)
            paths = []
            for i in range(12):
                png_type = getattr(
                    __import__("AppKit", fromlist=["NSBitmapImageFileType"]),
                    "NSBitmapImageFileTypePNG", None)
                img = self._draw_spinner(i * (360 // 12))
                tiff = img.TIFFRepresentation()
                out = frames_dir / f"frame{i}.png"
                if png_type is not None:
                    rep = NSBitmapImageRep.imageRepWithData_(tiff)
                    data = rep.representationUsingType_properties_(png_type, {})
                else:
                    out = frames_dir / f"frame{i}.tiff"
                    data = tiff
                data.writeToFile_atomically_(str(out), True)
                if out.exists():
                    paths.append(str(out))
            self._icon_frames = paths or None
        except Exception as e:
            self._debug(f"_busy_frames failed: {e}")
            self._icon_frames = None
        return self._icon_frames

    def _start_busy(self, note="Working..."):
        """Show the animated tray icon while an operation runs.

        Two visible indicators fire simultaneously:
          1. The menu-bar *title* text changes to `note` (default "Working…").
          2. The tray *icon* starts spinning through pre-rendered frames.
        """
        self._busy += 1
        if self._busy == 1:
            self._busy_frames()          # cache frame paths (best-effort)
            self._anim_index = 0
            # Show a visible label next to the icon immediately.
            try:
                self.title = BUSY_BUSY_TEXT
            except Exception:
                pass
            try:
                if self._anim_timer is None:
                    self._anim_timer = rumps.Timer(self._anim_tick, 0.08)
                self._anim_tick(None)    # show frame #0 immediately
                self._anim_timer.start()
            except Exception as e:
                self._debug(f"_start_busy timer failed: {e}")
        if note:
            try:
                self.last_run_item.title = note
            except Exception:
                pass

    def _stop_busy(self):
        """Restore the normal tray icon when the operation finishes."""
        self._busy = max(0, self._busy - 1)
        if self._busy == 0:
            if self._anim_timer is not None:
                try:
                    self._anim_timer.stop()
                except Exception:
                    pass
            try:
                self.icon = self._base_icon
                self.title = ""            # clear the "Working…" title
            except Exception:
                pass
        self.update_last_run_ui()

    def _anim_tick(self, timer=None):
        """Timer callback: advance the rotating icon frames while busy.

        The menu-bar *title* is set once to BUSY_BUSY_TEXT in _start_busy and
        left unchanged — it's the static "Working…" label the user sees.  This
        method only rotates the *icon* (the actual image) so the download-arrow
        spins.
        """
        if self._busy <= 0:
            return
        i = self._anim_index
        frames = self._icon_frames or []
        if frames:
            try:
                self.icon = frames[i % len(frames)]   # rumps wants a path str
            except Exception as e:
                self._debug(f"icon set failed: {e}")
        self._anim_index += 1

    # ---- Greeting & about -------------------------------------------------

    def _startup_greeting(self):
        """Welcome first-time users; nudge everyone towards the menu-bar icon.

        The modal shows once per app VERSION (not just once ever), so it also
        appears after installing an update — while never re-appearing every
        launch on the same version.
        """
        settings = organize_downloads.load_settings()
        shown_for = settings.get("welcomed_version")
        first_time = shown_for != APP_VERSION

        # Small reminder on every launch so the app never feels "invisible".
        # NOTE: rumps.Timer repeats forever until .stop() — hence _once().
        def notify(t=None):
            t.stop() if t is not None else None
            rumps.notification(
                APP_NAME, "I'm up here ☝️",
                "Click the ⬇ arrow icon in your menu bar to organize your files."
            )
        rumps.Timer(notify, 0.8).start()

        if first_time:
            def welcome(t=None):
                try:
                    if t is not None:
                        t.stop()
                    rumps.alert(
                        title=f"Welcome to {APP_NAME}!",
                        message="FileFlow lives in your menu bar, look for the "
                                "little arrow icon at the top-right of your screen.\n\n"
                                "Click it any time to:\n\n"
                                "  Organize Now: sort loose files into folders\n"
                                "  Auto-Organize: sort new downloads automatically\n"
                                "  Undo, Tools, Rules and more\n\n"
                                "First launch? If macOS says FileFlow can't be "
                                "opened, right-click it, then Open, then click Open.\n\n"
                                f"Made with love by {APP_AUTHOR}",
                    )
                    # Mark as greeted for THIS version only after the user
                    # closes the modal once.
                    s = organize_downloads.load_settings()
                    if s.get("welcomed_version") != APP_VERSION:
                        s["welcomed"] = True
                        s["welcomed_version"] = APP_VERSION
                        organize_downloads.save_settings(s)
                except Exception:
                    pass
            rumps.Timer(welcome, 1.2).start()

    def show_welcome(self, sender=None):
        """Re-open the welcome guide on demand (menu item)."""
        rumps.alert(
            title=f"Welcome to {APP_NAME}!",
            message="FileFlow lives in your menu bar, look for the "
                    "little arrow icon at the top-right of your screen.\n\n"
                    "Click it any time to:\n\n"
                    "  Organize Now: sort loose files into folders\n"
                    "  Auto-Organize: sort new downloads automatically\n"
                    "  Undo, Tools, Rules and more\n\n"
                    "When FileFlow is working, the icon spins so you know "
                    "it is busy.\n\n"
                    f"Made with love by {APP_AUTHOR}",
        )

    # ---- Pro / License ----------------------------------------------------

    def _require_pro(self, feature_name=None):
        """Return True if Pro is active, else show an upgrade prompt and return False."""
        if license_mod.is_pro():
            return True
        title = f"Pro Feature"
        msg = (f"{feature_name} is a Pro feature.\n\n"
               f"Upgrade to FileFlow Pro for $8 (one-time) to unlock:\n\n"
               f"  Duplicate Finder\n"
               f"  Deep Scan\n"
               f"  Archive Old Files\n"
               f"  Unlimited Rules and Folders\n\n"
               f"Click Get Pro in the menu to learn more.")
        rumps.alert(title=title, message=msg)
        return False

    def show_get_pro(self, sender=None):
        """Show the Pro upgrade dialog with license activation."""
        if license_mod.is_pro():
            info = license_mod.get_license_info()
            key = info.get('key', '')
            rumps.alert(
                title="FileFlow Pro Active",
                message=f"You are a Pro user!\n\n"
                        f"License: {key[:8]}...\n\n"
                        f"Thank you for supporting FileFlow."
            )
            return

        resp = rumps.alert(
            title="FileFlow Pro, $8 one-time",
            message="Unlock power tools:\n\n"
                    "  Duplicate Finder: find and clean up duplicates\n"
                    "  Deep Scan: look inside organized folders\n"
                    "  Archive Old Files: auto-move old installers\n"
                    "  Unlimited Rules and Folders\n\n"
                    "Buy a license key at:\n"
                    f"{license_mod.get_checkout_url()}\n\n"
                    "Then enter your key below.",
            ok="Enter Key",
            cancel="Not Now"
        )
        if resp:
            w = rumps.Window(
                message="Paste your Pro license key:",
                title="Activate FileFlow Pro",
                default_text="",
                dimensions=(360, 32)
            )
            r = w.run()
            if r.clicked and r.text.strip():
                result = license_mod.validate_license_key(r.text.strip())
                if result.get("valid"):
                    rumps.alert(title="Pro Activated", message="FileFlow Pro is now active on this Mac.")
                    self._build_tools_menu()
                    self.refresh_folders_menu()
                    self.refresh_rules_menu()
                    self.get_pro_item.title = "Pro Active"
                else:
                    rumps.alert(title="Activation Failed", message=result.get('error', 'Invalid key.'))

    def show_about(self, sender=None):
        pro_status = "Pro" if license_mod.is_pro() else "Free"
        rumps.alert(
            title=f"{APP_NAME} v{APP_VERSION}",
            message=f"A safe, tiny file organizer that lives in your menu bar.\n\n"
                    f"Developer: {APP_AUTHOR}\n"
                    f"License: {pro_status}\n"
                    f"It only ever moves files, never deletes.",
        )

    def show_support(self, sender=None):
        """Show support info for license issues and help."""
        resp = rumps.alert(
            title="Support",
            message="Having issues with your license key or the app?\n\n"
                    "Email: imulep2104@gmail.com\n"
                    "Subject: FileFlow Support\n\n"
                    "Please include:\n"
                    "  - Your license key (if applicable)\n"
                    "  - What you were trying to do\n"
                    "  - Any error message you saw\n\n"
                    "We usually reply within 24 hours.",
            ok="Copy Email",
            cancel="Close"
        )
        if resp == 0:
            # Copy email to clipboard
            import subprocess
            subprocess.run(["pbcopy"], input=b"imulep2104@gmail.com")

    def quit_app(self, sender=None):
        """Stop the timer, restore the icon and exit cleanly."""
        try:
            if self._anim_timer is not None:
                self._anim_timer.stop()
            self.timer.stop()
        except Exception:
            pass
        rumps.quit_application()

    def _roots(self):
        """All roots (Downloads + extras) as a list of Paths."""
        return organize_downloads.resolve_roots(None)

    def _build_tools_menu(self):
        self._safe_clear(self.tools_item)
        self.tools_item.title = "Tools"
        is_pro = license_mod.is_pro()
        self.deep_scan_item = rumps.MenuItem(
            "Deep Scan (include grouped folders)", callback=self.toggle_deep_scan)
        self.deep_scan_item.state = 1 if self._deep_scan_enabled() else 0
        _set_menu_icon(self.deep_scan_item, "icon-pro-crown")

        pro_items = [
            ("Find Duplicates", self.scan_duplicates),
            ("Move duplicates to _Duplicates", self.move_duplicates),
            ("Archive Old Installers (90d)", self.archive_now),
        ]
        free_items = [
            ("Biggest Files", self.show_biggest),
        ]
        self.tools_item.add(self.deep_scan_item)
        self.tools_item.add(rumps.separator)
        for label, cb in pro_items:
            it = rumps.MenuItem(label, callback=cb)
            _set_menu_icon(it, "icon-pro-crown")
            self.tools_item.add(it)
        self.tools_item.add(rumps.separator)
        for label, cb in free_items:
            it = rumps.MenuItem(label, callback=cb)
            self.tools_item.add(it)

    def _deep_scan_enabled(self) -> bool:
        return bool(organize_downloads.load_settings().get("deep_scan"))

    def toggle_deep_scan(self, sender=None):
        """Toggle whether Tools also look INSIDE grouped folders."""
        if not self._require_pro("Deep Scan"):
            return
        s = organize_downloads.load_settings()
        new_val = not bool(s.get("deep_scan"))
        s["deep_scan"] = new_val
        organize_downloads.save_settings(s)
        if hasattr(self, "deep_scan_item"):
            self.deep_scan_item.state = 1 if new_val else 0
        if new_val:
            rumps.notification(
                "FileFlow", "Deep Scan: ON",
                "Tools will now look inside organized folders too "
                "(bookkeeping folders like _Duplicates are skipped).")
        else:
            rumps.notification(
                "FileFlow", "Deep Scan: OFF",
                "Tools will only look at loose files at the top level.")

    # ---- Duplicates -------------------------------------------------------

    def scan_duplicates(self, sender=None):
        if not self._require_pro("Duplicate Finder"):
            return
        def work():
            try:
                roots = self._roots()
                groups = organize_downloads.find_duplicates(roots, deep=self._deep_scan_enabled())
            except Exception as e:
                self._post_ui(lambda: self.notify("Duplicates", f"Scan failed: {e}"))
            else:
                self._post_ui(lambda: self._duplicates_result(groups))
            finally:
                self._stop_busy()
        self._start_busy("Scanning for duplicates…")
        threading.Thread(target=work).start()

    def _duplicates_result(self, groups):
        """Show the duplicate scan result, runs on the main thread."""
        if not groups:
            self.notify("No duplicates", "No duplicate files found.")
            return
        copies = sum(len(g["files"]) - 1 for g in groups)
        bytes_ = sum((len(g["files"]) - 1) * g["size"] for g in groups)
        detail = self._human_size(bytes_)
        examples = groups[:3]
        lines = "\n".join(f"  • {g['name']} (x{len(g['files'])})" for g in examples)
        more = f"\n  …and {len(groups)-len(examples)} more group(s)" \
            if len(groups) > len(examples) else ""
        rumps.alert(title=f"{copies} duplicate copy/copies found",
                    message=f"~{detail} of wasted space.\n{lines}{more}")

    def move_duplicates(self, event=None):
        if not self._require_pro("Duplicate Finder"):
            return
        self._move_duplicates_confirmed()

    def _move_duplicates_confirmed(self):
        def run():
            try:
                roots = self._roots()
                stats = organize_downloads.move_duplicates(roots, dry_run=False, deep=self._deep_scan_enabled())
            except Exception as e:
                self._post_ui(lambda: self.notify("Duplicates", f"Failed: {e}"))
            else:
                self._post_ui(lambda: self.notify(
                    "Duplicates moved",
                    f"Moved {stats['moved']} duplicate(s), "
                    f"freeing ~{self._human_size(stats['bytes'])}."))
            finally:
                self._stop_busy()
        self._start_busy("Moving duplicates…")
        threading.Thread(target=run).start()

    def show_biggest(self, sender=None):
        def run():
            try:
                roots = self._roots()
                items = organize_downloads.biggest_files(roots, 15, deep=self._deep_scan_enabled())
            except Exception as e:
                self._post_ui(lambda: self.notify("Biggest files", f"Failed: {e}"))
            else:
                lines = [f"{self._human_size(it['size']):>9}  {it['category']:12} {it['name']}"
                         for it in items]
                self._post_ui(lambda: rumps.alert(
                    title=f"Top {len(items)} largest files",
                    message="\n".join(lines) or "No loose files found."))
            finally:
                self._stop_busy()
        self._start_busy("Measuring…")
        threading.Thread(target=run).start()

    def archive_now(self, sender=None):
        """Confirm, then archive Installers/Archives older than 90 days."""
        if not self._require_pro("Archive Old Files"):
            return
        resp = rumps.alert(title="Archive old installers?",
                           message="Move Installers/Archives older than 90 days "
                                   "into _Old_ folders? (Nothing is deleted.)",
                           ok="Archive", cancel="Cancel")
        if not resp:
            return
        def run():
            try:
                roots = self._roots()
                stats = organize_downloads.archive_old(roots, days=90, dry_run=False)
            except Exception as e:
                self._post_ui(lambda: self.notify("Archive", f"Failed: {e}"))
            else:
                self._post_ui(lambda: self.notify(
                    "Old files archived",
                    f"Moved {stats['moved']} old file(s), "
                    f"freeing ~{self._human_size(stats['bytes'])}."))
            finally:
                self._stop_busy()
        self._start_busy("Archiving old installers…")
        threading.Thread(target=run).start()

    def refresh_rules_menu(self):
        """Rebuild the 'Rules ▸' submenu from settings."""
        self._safe_clear(self.rules_item)
        rules = organize_downloads.load_rules()
        self.rules_item.title = f"Rules ({len(rules)})"
        if not rules:
            self.rules_item.add(rumps.MenuItem("No rules yet", callback=None))
        else:
            for r in rules:
                m = "name contains" if r.get("match") == "keyword" else "ends with"
                v = r.get("value") or ""
                d = r.get("dest") or ""
                item = rumps.MenuItem(f"✕  {m} “{v}” → {d}")
                item.set_callback(lambda _, rule=r: self.remove_rule(rule))
                self.rules_item.add(item)
        self.rules_item.add(rumps.separator)
        add = rumps.MenuItem("+ Add a rule…", callback=self.add_rule)
        self.rules_item.add(add)

    def remove_rule(self, rule):
        rules = organize_downloads.load_rules()
        if rule in rules:
            rules.remove(rule)
            organize_downloads.save_rules(rules)
            self.refresh_rules_menu()
            rumps.notification("FileFlow", "Rule removed",
                               f"No longer sending {rule.get('value')} to "
                               f"{rule.get('dest')}.")

    def add_rule(self, sender=None):
        rules = organize_downloads.load_rules()
        if not license_mod.is_pro() and len(rules) >= 3:
            self._require_pro("Unlimited Custom Rules")
            return
        kind = rumps.alert(title="New rule",
                           message="Match files by extension (e.g. iso) or by a "
                                   "word in the name?",
                           ok="By extension", cancel="By name")
        match = "suffix" if kind else "keyword"
        label = "extension (type: iso, pdf, …)" if match == "suffix" \
            else "word in the name (e.g. invoice)"
        w1 = rumps.Window(message=f"Match on {label}",
                          title="FileFlow — New rule",
                          default_text="", dimensions=(360, 32))
        r1 = w1.run()
        if not (r1.clicked and r1.text.strip()):
            return
        value = r1.text.strip()
        w2 = rumps.Window(message="Move matches into folder?",
                          title="e.g.  ISOs, Finance, Comics",
                          default_text="", dimensions=(360, 32))
        r2 = w2.run()
        if not (r2.clicked and r2.text.strip()):
            return
        dest = r2.text.strip().lstrip("/\\")
        if not dest:
            return
        rules = organize_downloads.load_rules()
        rules.append({"match": match, "value": value, "dest": dest})
        organize_downloads.save_rules(rules)
        self.refresh_rules_menu()
        rumps.notification("FileFlow", "Rule added",
                           f"{value} → {dest}")

    # ---- Launch at login -------------------------------------------------

    def update_launch_login_state(self):
        self.launch_login_item.state = 1 if LOGIN_PLIST.exists() else 0

    def toggle_launch_login(self, sender):
        if LOGIN_PLIST.exists():
            try:
                subprocess.run(["launchctl", "unload", str(LOGIN_PLIST)],
                               capture_output=True)
                LOGIN_PLIST.unlink()
                rumps.notification("FileFlow", "Launch at login: off",
                                   "FileFlow will no longer open at login.")
            except Exception as e:
                rumps.alert(title="Error", message=f"Failed to disable: {e}")
        else:
            try:
                exe = self._app_executable()
                plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.fileflow.login</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
                LOGIN_PLIST.parent.mkdir(parents=True, exist_ok=True)
                LOGIN_PLIST.write_text(plist_content)
                subprocess.run(["launchctl", "load", str(LOGIN_PLIST)],
                               capture_output=True)
                rumps.notification("FileFlow", "Launch at login: on",
                                   "FileFlow will open automatically when you "
                                   "log in.")
            except Exception as e:
                rumps.alert(title="Error", message=f"Failed to enable: {e}")
        self.update_launch_login_state()

    def _app_executable(self):
        """The path launchd should run to start the FileFlow menu-bar app."""
        return str(Path(sys.executable).resolve())


    def _human_size(self, n: float) -> str:
        return organize_downloads._human_size(n)

    def view_log(self, sender):
        """Open the log file using system default application (Console or TextEdit)."""
        if LOG_FILE.exists():
            subprocess.run(["open", str(LOG_FILE)])
        else:
            rumps.alert(title="No Log File", message="No activity log has been created yet. Run the organizer first!")

if __name__ == "__main__":
    FileFlowApp().run()
