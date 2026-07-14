import os
import sys
import time
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
import rumps

# Define Paths
LOG_DIR = Path.home() / ".file-organizer"
LOG_FILE = LOG_DIR / "activity.log"
STATE_FILE = LOG_DIR / "last_run.json"
PLIST_PATH = Path.home() / "Library/LaunchAgents/com.user.downloadsorganizer.plist"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class DownloadsOrganizerApp(rumps.App):
    def __init__(self):
        try:
            with open("/tmp/menu_bar_debug.log", "a") as f:
                f.write("DownloadsOrganizerApp __init__ started\n")
        except Exception as e:
            pass
        super(DownloadsOrganizerApp, self).__init__("Downloads Organizer", icon=resource_path("status_iconTemplate.png"), template=True)
        
        # Initialize menu items
        self.last_run_item = rumps.MenuItem("Last Run: Checking...", callback=None)
        self.organize_now_item = rumps.MenuItem("Organize Now", callback=self.organize_now)
        self.toggle_auto_item = rumps.MenuItem("Auto-Organize in Background", callback=self.toggle_auto)
        self.view_log_item = rumps.MenuItem("View Activity Log", callback=self.view_log)
        
        # Build menu
        self.menu = [
            self.last_run_item,
            rumps.separator,
            self.organize_now_item,
            self.toggle_auto_item,
            self.view_log_item,
            rumps.separator
        ]
        
        # Set initial auto-organize check state
        self.update_auto_state()
        
        # Load initial last run state
        self.update_last_run_ui()
        
        # Start a periodic timer to update the last run time text (every 30 seconds)
        self.timer = rumps.Timer(self.periodic_update, 30)
        self.timer.start()
        try:
            with open("/tmp/menu_bar_debug.log", "a") as f:
                f.write("DownloadsOrganizerApp __init__ completed successfully\n")
        except Exception as e:
            pass

    def get_bin_path(self):
        """Returns the absolute path to DownloadsOrganizer-Mac binary."""
        # If running from inside a PyInstaller .app bundle
        if getattr(sys, 'frozen', False):
            # sys.executable is inside DownloadsOrganizer.app/Contents/MacOS/DownloadsOrganizer
            # The companion CLI DownloadsOrganizer-Mac should be next to DownloadsOrganizer.app
            app_dir = Path(sys.executable).parent.parent.parent.parent
            bin_path = app_dir / "DownloadsOrganizer-Mac"
            if bin_path.exists():
                return bin_path
        
        # Fallback to dev python script
        dev_script = Path(__file__).parent / "organize_downloads.py"
        if dev_script.exists():
            return dev_script
        return None

    def update_auto_state(self):
        """Checks launchd plist to set menu item checkbox state."""
        self.toggle_auto_item.state = 1 if PLIST_PATH.exists() else 0

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

    def organize_now(self, sender):
        """Trigger file organizer in a separate thread so UI does not freeze."""
        self.organize_now_item.title = "Organizing..."
        self.organize_now_item.set_callback(None) # Disable clicks during run
        
        threading.Thread(target=self.run_organization_thread).start()

    def run_organization_thread(self):
        """Worker thread to run sorting logic and redirect output."""
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            
            # Use direct import and run logic inside Python rather than calling subprocess
            # This is cleaner and updates the state file directly
            import sys as pysys
            from contextlib import redirect_stdout, redirect_stderr
            import organize_downloads
            
            with open(LOG_FILE, "a") as log:
                log.write(f"\n--- Menu-Bar Triggered Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                with redirect_stdout(log), redirect_stderr(log):
                    # Mock args to point to default Downloads folder
                    organize_downloads.main([])
                    
        except Exception as e:
            # Fallback output to log
            try:
                with open(LOG_FILE, "a") as log:
                    log.write(f"Error during organization run: {e}\n")
            except:
                pass
        finally:
            # Update GUI back on main thread safely
            def cleanup():
                self.organize_now_item.title = "Organize Now"
                self.organize_now_item.set_callback(self.organize_now)
                self.update_last_run_ui()
                
            rumps.notification("Downloads Organizer", "Finished sorting", "Loose files in ~/Downloads have been organized.")
            # Trigger callback on main thread UI
            rumps.Timer(lambda t: cleanup(), 0.1).start()

    def toggle_auto(self, sender):
        """Enables or disables launchd auto-organization plist."""
        bin_path = self.get_bin_path()
        if not bin_path:
            rumps.alert(title="Error", message="Could not find executable binary to schedule background task.")
            return

        # If currently enabled, disable it
        if PLIST_PATH.exists():
            try:
                # Unload launchd
                subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
                PLIST_PATH.unlink()
                rumps.notification("Downloads Organizer", "Auto-Organize Disabled", "Background service stopped.")
            except Exception as e:
                rumps.alert(title="Error", message=f"Failed to disable auto-organize: {e}")
        else:
            # Enable it
            try:
                # Determine standard shell script vs compiled binary arguments for launchd plist
                if bin_path.suffix == ".py":
                    args = [
                        "/usr/bin/python3",
                        str(bin_path.resolve())
                    ]
                else:
                    args = [
                        str(bin_path.resolve())
                    ]

                # Format launchd Plist
                plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.downloadsorganizer</string>
    <key>ProgramArguments</key>
    <array>
        {"".join(f"<string>{arg}</string>" for arg in args)}
    </array>
    <key>WatchPaths</key>
    <array>
        <string>{os.path.expanduser('~/Downloads')}</string>
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
                with open(PLIST_PATH, "w") as f:
                    f.write(plist_content)
                
                # Load launchd
                subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True)
                rumps.notification("Downloads Organizer", "Auto-Organize Enabled", "Your downloads will now be organized automatically.")
            except Exception as e:
                rumps.alert(title="Error", message=f"Failed to enable auto-organize: {e}")
                if PLIST_PATH.exists():
                    PLIST_PATH.unlink()

        self.update_auto_state()

    def view_log(self, sender):
        """Open the log file using system default application (Console or TextEdit)."""
        if LOG_FILE.exists():
            subprocess.run(["open", str(LOG_FILE)])
        else:
            rumps.alert(title="No Log File", message="No activity log has been created yet. Run the organizer first!")

if __name__ == "__main__":
    DownloadsOrganizerApp().run()
