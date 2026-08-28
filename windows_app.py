#!/usr/bin/env python3
"""FileDocket Windows tray app.

Lives in the notification area. Organize Now runs the same sorter as macOS.
Auto-Organize is a scheduled task that calls this exe with --organize.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import organize_downloads

APP_NAME = "FileDocket"
TASK_NAME = "FileDocket"
STATE_FILE = Path.home() / ".file-organizer" / "last_run.json"
DOWNLOADS = Path.home() / "Downloads"


def resource_path(name: str) -> str:
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, name)


def app_exe() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def run_organize() -> None:
    organize_downloads.main([])


def last_run_label() -> str:
    if not STATE_FILE.exists():
        return "Last Run: Never"
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        ts = data.get("timestamp")
        moved = data.get("moved", 0)
        if not ts:
            return "Last Run: Never"
        when = datetime.fromtimestamp(float(ts)).strftime("%b %d %H:%M")
        return f"Last Run: {when} ({moved} moved)"
    except Exception:
        return "Last Run: Never"


def task_exists() -> bool:
    r = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def enable_auto() -> None:
    if getattr(sys, "frozen", False):
        helper = Path(sys.executable).resolve().parent / "organize.cmd"
        tr = f'"{helper}"' if helper.is_file() else f"{app_exe()} --organize"
    else:
        tr = f"{app_exe()} --organize"
    subprocess.run(
        ["schtasks", "/create", "/tn", TASK_NAME, "/tr", tr,
         "/sc", "minute", "/mo", "15", "/f"],
        check=True, capture_output=True, text=True,
    )


def disable_auto() -> None:
    subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True, text=True,
    )


def startup_lnk() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "FileDocket.lnk"


def launch_at_login() -> bool:
    return startup_lnk().exists()


def set_launch_at_login(on: bool) -> None:
    lnk = startup_lnk()
    if not on:
        try:
            lnk.unlink()
        except FileNotFoundError:
            pass
        return
    lnk.parent.mkdir(parents=True, exist_ok=True)
    target = sys.executable if getattr(sys, "frozen", False) else sys.executable
    args = "" if getattr(sys, "frozen", False) else str(Path(__file__).resolve())
    workdir = str(Path(target).parent)
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{str(lnk).replace(chr(39), chr(39)+chr(39))}'); "
        f"$s.TargetPath = '{target.replace(chr(39), chr(39)+chr(39))}'; "
        f"$s.Arguments = '{args.replace(chr(39), chr(39)+chr(39))}'; "
        f"$s.WorkingDirectory = '{workdir.replace(chr(39), chr(39)+chr(39))}'; "
        "$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True)


def load_tray_image():
    from PIL import Image
    for name in ("status_iconTemplate.png", "filedocket.ico"):
        p = resource_path(name)
        if os.path.isfile(p):
            return Image.open(p)
    return Image.new("RGBA", (64, 64), (0, 168, 196, 255))


def start_tray() -> None:
    import pystray
    from pystray import MenuItem as Item

    icon_holder = {"icon": None}

    def notify(title: str, message: str) -> None:
        ic = icon_holder["icon"]
        if ic is not None:
            try:
                ic.notify(message, title)
            except Exception:
                pass

    def refresh(_icon=None) -> None:
        ic = icon_holder["icon"]
        if ic is None:
            return
        ic.menu = build_menu()
        ic.update_menu()

    def on_organize(icon, _item) -> None:
        def work():
            try:
                run_organize()
                data = {}
                if STATE_FILE.exists():
                    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                moved = data.get("moved", 0)
                if moved:
                    notify(APP_NAME, f"Organized {moved} file(s).")
                else:
                    notify(APP_NAME, "No loose files to organize.")
            except Exception as e:
                notify(APP_NAME, f"Organize failed: {e}")
            refresh()
        threading.Thread(target=work, daemon=True).start()

    def on_auto(icon, item) -> None:
        try:
            if task_exists():
                disable_auto()
                notify(APP_NAME, "Auto-Organize off.")
            else:
                enable_auto()
                notify(APP_NAME, "Auto-Organize on — every 15 minutes.")
        except Exception as e:
            notify(APP_NAME, f"Could not update Auto-Organize: {e}")
        refresh()

    def on_undo(icon, _item) -> None:
        try:
            entry = organize_downloads.undo_last()
            if entry:
                notify(APP_NAME, f"Restored {entry.get('orig', 'file')}.")
            else:
                notify(APP_NAME, "Nothing to undo.")
        except Exception as e:
            notify(APP_NAME, f"Undo failed: {e}")
        refresh()

    def on_login(icon, item) -> None:
        try:
            set_launch_at_login(not launch_at_login())
        except Exception as e:
            notify(APP_NAME, f"Could not update login item: {e}")
        refresh()

    def on_add_folder(icon, _item) -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            chosen = filedialog.askdirectory(title="Folder to organize")
            root.destroy()
        except Exception as e:
            notify(APP_NAME, f"Could not pick a folder: {e}")
            return
        if not chosen:
            return
        folder = Path(chosen)
        extras = organize_downloads.load_extra_roots()
        if folder in extras or folder == DOWNLOADS:
            notify(APP_NAME, "That folder is already included.")
            return
        if len(extras) >= 1:
            notify(APP_NAME, "Free includes one extra folder. Pro unlocks more.")
            return
        extras.append(folder)
        organize_downloads.save_extra_roots(extras)
        notify(APP_NAME, f"Added {folder.name}.")
        refresh()

    def on_downloads(icon, _item) -> None:
        if DOWNLOADS.is_dir():
            os.startfile(str(DOWNLOADS))  # type: ignore[attr-defined]

    def on_quit(icon, _item) -> None:
        icon.stop()

    def build_menu():
        auto_on = task_exists()
        login_on = launch_at_login()
        return pystray.Menu(
            Item(last_run_label(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            Item("Organize Now", on_organize),
            Item("Auto-Organize every 15 minutes", on_auto, checked=lambda _: auto_on),
            Item("Undo Last Move", on_undo),
            pystray.Menu.SEPARATOR,
            Item("Open Downloads", on_downloads),
            Item("Add a folder…", on_add_folder),
            Item("Launch FileDocket at login", on_login, checked=lambda _: login_on),
            pystray.Menu.SEPARATOR,
            Item("Quit FileDocket", on_quit),
        )

    icon = pystray.Icon(
        APP_NAME,
        load_tray_image(),
        APP_NAME,
        build_menu(),
    )
    icon_holder["icon"] = icon
    icon.run()


def main() -> int:
    if "--organize" in sys.argv:
        run_organize()
        return 0
    if sys.platform != "win32":
        print("This tray app is for Windows. On macOS use FileDocket.app.")
        return 1
    start_tray()
    return 0


if __name__ == "__main__":
    sys.exit(main())
