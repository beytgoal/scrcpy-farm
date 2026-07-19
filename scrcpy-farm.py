#!/usr/bin/env python3
"""
Scrcpy Farm v4.0 — Modern Glass UI Android Device Farm Manager
Cross-Platform: Windows, Linux, macOS
scrcpy v4.1: includes adb.exe (no separate download needed)
"""

import os
import sys
import json
import subprocess
import platform
import threading
import time
import socket
import re
import shutil
import signal
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, simpledialog
except ImportError:
    print("ERROR: tkinter not found. Install python3-tk (Linux) or use official Python (Windows/macOS)")
    sys.exit(1)

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
    HAS_TTKBOOTSTRAP = True
except ImportError:
    HAS_TTKBOOTSTRAP = False

# =====================================================================
# PLATFORM DETECTION
# =====================================================================
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"

if IS_WINDOWS:
    APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    EXE_SCRCPY = APP_DIR / "scrcpy.exe"
    EXE_ADB = APP_DIR / "adb.exe"
    DEFAULT_SCRCPY = "C:\\scrcpy\\scrcpy.exe"
    DEFAULT_ADB = "C:\\scrcpy\\adb.exe"
    if EXE_SCRCPY.exists():
        DEFAULT_SCRCPY = str(EXE_SCRCPY)
    if EXE_ADB.exists():
        DEFAULT_ADB = str(EXE_ADB)
    SCRCPY_DIR = Path("C:\\scrcpy")
    PING_CMD = ["ping", "-n", "1", "-w", "200"]
    PING_TIMEOUT = 2
elif IS_MACOS:
    DEFAULT_SCRCPY = "/opt/homebrew/bin/scrcpy"
    DEFAULT_ADB = "/opt/homebrew/bin/adb"
    SCRCPY_DIR = Path.home() / "scrcpy-farm"
    if not Path(DEFAULT_SCRCPY).exists():
        DEFAULT_SCRCPY = "/usr/local/bin/scrcpy"
    if not Path(DEFAULT_ADB).exists():
        DEFAULT_ADB = "/usr/local/bin/adb"
    PING_CMD = ["ping", "-c", "1", "-W", "2"]
    PING_TIMEOUT = 3
else:
    DEFAULT_SCRCPY = "/usr/bin/scrcpy"
    DEFAULT_ADB = "/usr/bin/adb"
    SCRCPY_DIR = Path.home() / "scrcpy-farm"
    PING_CMD = ["ping", "-c", "1", "-W", "1"]
    PING_TIMEOUT = 2

SETTINGS_FILE = Path.home() / ".scrcpy-farm.json"

DEFAULTS = {
    "scrcpy_path": str(DEFAULT_SCRCPY),
    "adb_path": str(DEFAULT_ADB),
    "default_bitrate": "4M",
    "default_max_size": 1024,
    "default_max_fps": 30,
    "default_screen_off": True,
    "default_power_on_close": True,
    "grid_per_page": 20,
    "auto_reconnect": True,
    "check_interval": 5,
    "charge_mode": False,
    "auto_scan": True,
    "known_ips": [],
    "subnet": "192.168.1",
    "scan_range_start": 1,
    "scan_range_end": 254,
    "theme": "darkly",
}

# =====================================================================
# SETTINGS
# =====================================================================
def load_settings():
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE) as f:
                s = {**DEFAULTS, **json.load(f)}
                if not isinstance(s.get("known_ips"), list):
                    s["known_ips"] = []
                return s
    except Exception:
        pass
    return dict(DEFAULTS)

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

# =====================================================================
# HELPER: run subprocess safely
# =====================================================================
def run_cmd(cmd, timeout=15):
    """Run command, return stdout string."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
        )
        return r.stdout.strip()
    except Exception:
        return ""

# =====================================================================
# MAIN APPLICATION
# =====================================================================
class ScrcpyFarmApp:
    """Modern Android Device Farm Manager."""

    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.devices = {}          # serial -> info dict
        self.active_streams = {}   # serial -> scrcpy process
        self.grid_page = 0
        self.groups = {"All": [], "VIP": [], "Production": []}
        self.health_running = False
        self.current_theme = self.settings.get("theme", "darkly")

        # Check dependencies
        self.detect_paths()

        # Build UI
        self.build_ui()

        # Start health check
        self.start_health_check()

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    # -----------------------------------------------------------------
    # DEPENDENCY DETECTION
    # -----------------------------------------------------------------
    def detect_paths(self):
        """Check scrcpy + adb exist, show error if not."""
        sp = Path(self.settings.get("scrcpy_path", DEFAULT_SCRCPY))
        ap = Path(self.settings.get("adb_path", DEFAULT_ADB))
        missing = []
        if not sp.exists():
            missing.append("scrcpy")
        if not ap.exists():
            missing.append("adb")
        if missing:
            self._show_missing_dialog(missing)

    def _show_missing_dialog(self, missing):
        """Show error when dependencies are missing."""
        import tkinter.messagebox as mb
        msg = (
            f"Missing: {', '.join(missing)}\n\n"
            "Run setup.bat from the repo to install.\n"
            "Or install manually:\n"
            "  scrcpy: github.com/Genymobile/scrcpy/releases/latest\n"
            "  ADB: developer.android.com/tools/releases/platform-tools"
        )
        mb.showerror("Dependencies Missing", msg)

    def _show_download_dialog(self):
        """Legacy: no-op (deps now installed by setup.bat)."""
        pass

    # -----------------------------------------------------------------
    # UI BUILD
    # -----------------------------------------------------------------
    def build_ui(self):
        """Build the main application UI."""
        self.root.title("Scrcpy Farm v4.0")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 700)

        # Apply theme
        if HAS_TTKBOOTSTRAP:
            self.apply_theme(self.current_theme)
        else:
            self.root.configure(bg="#1a1a2e")

        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        # Header
        self.build_header()

        # Content area
        self.build_content()

        # Status bar
        self.build_status_bar()

    def apply_theme(self, theme_name):
        """Apply ttkbootstrap theme."""
        if HAS_TTKBOOTSTRAP:
            ttkb.Style(theme=theme_name)
            self.current_theme = theme_name
            self.settings["theme"] = theme_name
            save_settings(self.settings)

    def build_header(self):
        """Build app header with title and stats."""
        header = ttk.Frame(self.main_frame)
        header.pack(fill="x", padx=10, pady=5)

        # Title
        title = ttk.Label(header, text="Scrcpy Farm", font=("Segoe UI", 18, "bold"))
        title.pack(side="left")

        # Stats
        self.stats_frame = ttk.Frame(header)
        self.stats_frame.pack(side="right")

        self.stat_total = ttk.Label(self.stats_frame, text="Total: 0", font=("Segoe UI", 10))
        self.stat_total.pack(side="left", padx=10)

        self.stat_online = ttk.Label(self.stats_frame, text="Online: 0", foreground="green", font=("Segoe UI", 10))
        self.stat_online.pack(side="left", padx=10)

        self.stat_offline = ttk.Label(self.stats_frame, text="Offline: 0", foreground="red", font=("Segoe UI", 10))
        self.stat_offline.pack(side="left", padx=10)

        self.stat_mirror = ttk.Label(self.stats_frame, text="Mirror: 0", foreground="orange", font=("Segoe UI", 10))
        self.stat_mirror.pack(side="left", padx=10)

        # Settings button
        settings_btn = ttk.Button(header, text="Settings", command=self.open_settings)
        settings_btn.pack(side="right", padx=5)

        # Theme button
        theme_btn = ttk.Button(header, text="Theme", command=self.cycle_theme)
        theme_btn.pack(side="right", padx=5)

    def build_content(self):
        """Build main content area with device grid and groups."""
        content = ttk.Frame(self.main_frame)
        content.pack(fill="both", expand=True, padx=10, pady=5)

        # Left panel: device grid
        left = ttk.Frame(content)
        left.pack(side="left", fill="both", expand=True)

        # Grid controls
        grid_ctrl = ttk.Frame(left)
        grid_ctrl.pack(fill="x", pady=5)

        ttk.Label(grid_ctrl, text="Device Grid", font=("Segoe UI", 12, "bold")).pack(side="left")

        ttk.Button(grid_ctrl, text="Refresh", command=self.scan_devices).pack(side="right", padx=5)
        ttk.Button(grid_ctrl, text="Scan", command=self.scan_network).pack(side="right", padx=5)

        # Device grid canvas
        self.grid_canvas = tk.Canvas(left, bg="#1a1a2e", highlightthickness=0)
        self.grid_scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.grid_canvas.yview)
        self.grid_frame = ttk.Frame(self.grid_canvas)

        self.grid_frame.bind("<Configure>", lambda e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))
        self.grid_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_canvas.configure(yscrollcommand=self.grid_scrollbar.set)

        self.grid_scrollbar.pack(side="right", fill="y")
        self.grid_canvas.pack(fill="both", expand=True)

        # Pagination
        self.pagination_frame = ttk.Frame(left)
        self.pagination_frame.pack(fill="x", pady=5)
        self.update_pagination()

        # Right panel: groups
        right = ttk.Frame(content, width=250)
        right.pack(side="right", fill="y", padx=(10, 0))

        ttk.Label(right, text="Groups", font=("Segoe UI", 12, "bold")).pack(pady=5)

        self.group_listbox = tk.Listbox(right, font=("Segoe UI", 10), bg="#16213e", fg="white", selectbackground="#0f3460")
        self.group_listbox.pack(fill="both", expand=True)
        for g in self.groups:
            self.group_listbox.insert(tk.END, g)

        grp_btn_frame = ttk.Frame(right)
        grp_btn_frame.pack(fill="x", pady=5)
        ttk.Button(grp_btn_frame, text="+", width=3, command=self.new_group).pack(side="left", padx=2)
        ttk.Button(grp_btn_frame, text="-", width=3, command=self.del_group).pack(side="left", padx=2)

    def build_status_bar(self):
        """Build bottom status bar."""
        status = ttk.Frame(self.main_frame)
        status.pack(fill="x", side="bottom")

        self.status_label = ttk.Label(status, text="Ready", font=("Segoe UI", 9))
        self.status_label.pack(side="left", padx=10)

        self.ip_label = ttk.Label(status, text=f"Known IPs: {len(self.settings.get('known_ips', []))}", font=("Segoe UI", 9))
        self.ip_label.pack(side="right", padx=10)

    # -----------------------------------------------------------------
    # DEVICE MANAGEMENT
    # -----------------------------------------------------------------
    def scan_devices(self):
        """Scan for connected Android devices."""
        self.status_label.config(text="Scanning...")
        threading.Thread(target=self._scan_devices_thread, daemon=True).start()

    def _scan_devices_thread(self):
        """Background thread for device scanning."""
        adb = self.settings.get("adb_path", DEFAULT_ADB)
        output = run_cmd([adb, "devices", "-l"])
        new_devices = {}

        for line in output.split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                model = ""
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1]
                new_devices[serial] = {
                    "serial": serial,
                    "model": model,
                    "online": True,
                    "mirroring": serial in self.active_streams,
                }

        self.devices = new_devices
        self.root.after(0, self.refresh_ui)

    def refresh_ui(self):
        """Refresh the device grid and stats."""
        # Update stats
        total = len(self.devices)
        online = sum(1 for d in self.devices.values() if d["online"])
        mirror = sum(1 for d in self.devices.values() if d["mirroring"])

        self.stat_total.config(text=f"Total: {total}")
        self.stat_online.config(text=f"Online: {online}")
        self.stat_offline.config(text=f"Offline: {total - online}")
        self.stat_mirror.config(text=f"Mirror: {mirror}")

        # Refresh grid
        self.refresh_grid()

    def refresh_grid(self):
        """Refresh the device grid display."""
        # Clear current grid
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        # Get devices for current page
        per_page = self.settings.get("grid_per_page", 20)
        all_devs = list(self.devices.values())
        start = self.grid_page * per_page
        end = min(start + per_page, len(all_devs))
        page_devs = all_devs[start:end]

        # Create device cards
        cols = 5
        for i, dev in enumerate(page_devs):
            row = i // cols
            col = i % cols
            self.create_device_card(dev, row, col)

        self.update_pagination()

    def create_device_card(self, dev, row, col):
        """Create a device card widget."""
        card = ttk.Frame(self.grid_frame, relief="solid", borderwidth=1)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        # Status indicator
        status_color = "green" if dev["online"] else "red"
        status_dot = tk.Canvas(card, width=12, height=12, bg=status_color, highlightthickness=0)
        status_dot.pack(pady=(5, 0))

        # Model name
        model = dev["model"] or dev["serial"][:12]
        ttk.Label(card, text=model, font=("Segoe UI", 10, "bold")).pack()

        # Serial
        ttk.Label(card, text=dev["serial"], font=("Segoe UI", 8)).pack()

        # Buttons
        btn_frame = ttk.Frame(card)
        btn_frame.pack(pady=5)

        if dev["online"]:
            if dev["mirroring"]:
                ttk.Button(btn_frame, text="Stop", command=lambda s=dev["serial"]: self.stop_mirror(s)).pack(side="left", padx=2)
            else:
                ttk.Button(btn_frame, text="Mirror", command=lambda s=dev["serial"]: self.start_mirror(s)).pack(side="left", padx=2)
                ttk.Button(btn_frame, text="Sideload", command=lambda s=dev["serial"]: self.sideload_apk(s)).pack(side="left", padx=2)

    def update_pagination(self):
        """Update pagination controls."""
        for widget in self.pagination_frame.winfo_children():
            widget.destroy()

        total = len(self.devices)
        per_page = self.settings.get("grid_per_page", 20)
        total_pages = max(1, (total + per_page - 1) // per_page)

        ttk.Button(self.pagination_frame, text="<", command=self.prev_page).pack(side="left", padx=5)
        ttk.Label(self.pagination_frame, text=f"Page {self.grid_page + 1}/{total_pages}", font=("Segoe UI", 10)).pack(side="left")
        ttk.Button(self.pagination_frame, text=">", command=self.next_page).pack(side="left", padx=5)

    def prev_page(self):
        if self.grid_page > 0:
            self.grid_page -= 1
            self.refresh_grid()

    def next_page(self):
        total = len(self.devices)
        per_page = self.settings.get("grid_per_page", 20)
        if (self.grid_page + 1) * per_page < total:
            self.grid_page += 1
            self.refresh_grid()

    # -----------------------------------------------------------------
    # DEVICE OPERATIONS
    # -----------------------------------------------------------------
    def start_mirror(self, serial):
        """Start scrcpy mirroring for a device."""
        scrcpy = self.settings.get("scrcpy_path", DEFAULT_SCRCPY)
        adb = self.settings.get("adb_path", DEFAULT_ADB)

        # Validate paths
        if not Path(scrcpy).exists():
            self.status_label.config(text=f"ERROR: scrcpy not found at {scrcpy}")
            return
        if not Path(adb).exists():
            self.status_label.config(text=f"ERROR: adb not found at {adb}")
            return

        args = [scrcpy]
        args.append(f"--serial={serial}")
        args.append(f"--adb={adb}")
        args.append(f"--bit-rate={self.settings.get('default_bitrate', '4M')}")
        args.append(f"--max-size={self.settings.get('default_max_size', 1024)}")
        args.append(f"--max-fps={self.settings.get('default_max_fps', 30)}")

        if self.settings.get("default_screen_off", True):
            args.append("--turn-screen-off")
        if self.settings.get("default_power_on_close", True):
            args.append("--power-off-on-close")

        try:
            # scrcpy must run from its own directory (needs scrcpy-server)
            cwd = str(Path(scrcpy).parent)
            proc = subprocess.Popen(
                args,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )
            self.active_streams[serial] = proc
            self.devices[serial]["mirroring"] = True
            self.refresh_ui()
            self.status_label.config(text=f"Mirroring {serial}")

            # Watch for process exit and capture errors
            threading.Thread(target=self._watch_process, args=(serial, proc), daemon=True).start()

        except Exception as e:
            self.status_label.config(text=f"ERROR: {e}")

    def _watch_process(self, serial, proc):
        """Watch scrcpy process and clean up on exit."""
        stderr_data = proc.stderr.read() if proc.stderr else ""
        proc.wait()
        if serial in self.active_streams:
            del self.active_streams[serial]
        if serial in self.devices:
            self.devices[serial]["mirroring"] = False
        if proc.returncode != 0 and stderr_data:
            self.root.after(0, lambda: self.status_label.config(text=f"scrcpy error: {stderr_data[:200]}"))
        self.root.after(0, self.refresh_ui)

    def stop_mirror(self, serial):
        """Stop scrcpy mirroring."""
        if serial in self.active_streams:
            proc = self.active_streams[serial]
            try:
                if IS_WINDOWS:
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGTERM)
            except Exception:
                pass
            del self.active_streams[serial]
        if serial in self.devices:
            self.devices[serial]["mirroring"] = False
        self.refresh_ui()

    def stop_all_mirrors(self):
        """Stop all active mirrors."""
        for serial in list(self.active_streams.keys()):
            self.stop_mirror(serial)

    def sideload_apk(self, serial):
        """Sideload APK to device."""
        from tkinter import filedialog
        apk_path = filedialog.askopenfilename(filetypes=[("APK files", "*.apk")])
        if apk_path:
            adb = self.settings.get("adb_path", DEFAULT_ADB)
            result = run_cmd([adb, "-s", serial, "install", "-r", apk_path], timeout=60)
            if "Success" in result:
                self.status_label.config(text=f"Installed on {serial}")
            else:
                self.status_label.config(text=f"Install failed: {result}")

    # -----------------------------------------------------------------
    # NETWORK SCANNING
    # -----------------------------------------------------------------
    def scan_network(self):
        """Scan network for Android devices."""
        self.status_label.config(text="Scanning network...")
        threading.Thread(target=self._scan_network_thread, daemon=True).start()

    def _scan_network_thread(self):
        """Background thread for network scanning."""
        subnet = self.settings.get("subnet", "192.168.1")
        start = self.settings.get("scan_range_start", 1)
        end = self.settings.get("scan_range_end", 254)

        found = []
        for i in range(start, end + 1):
            ip = f"{subnet}.{i}"
            result = run_cmd(PING_CMD + [ip], timeout=PING_TIMEOUT)
            if result and ("TTL=" in result or "ttl=" in result):
                found.append(ip)

        # Save found IPs
        known = self.settings.get("known_ips", [])
        for ip in found:
            if ip not in known:
                known.append(ip)
        self.settings["known_ips"] = known
        save_settings(self.settings)

        self.root.after(0, lambda: self.status_label.config(text=f"Found {len(found)} devices"))
        self.root.after(0, self.refresh_ui)

    # -----------------------------------------------------------------
    # SETTINGS
    # -----------------------------------------------------------------
    def open_settings(self):
        """Open settings dialog."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Settings")
        dlg.geometry("500x600")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        # Title
        ttk.Label(dlg, text="Settings", font=("Segoe UI", 14, "bold")).pack(pady=10)

        # Scrollable frame
        canvas = tk.Canvas(dlg)
        scrollbar = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Settings fields
        fields = [
            ("scrcpy_path", "Scrcpy Path", self.settings.get("scrcpy_path", DEFAULT_SCRCPY)),
            ("adb_path", "ADB Path", self.settings.get("adb_path", DEFAULT_ADB)),
            ("default_bitrate", "Default Bitrate", self.settings.get("default_bitrate", "4M")),
            ("default_max_size", "Max Resolution", self.settings.get("default_max_size", 1024)),
            ("default_max_fps", "Max FPS", self.settings.get("default_max_fps", 30)),
            ("grid_per_page", "Devices Per Page", self.settings.get("grid_per_page", 20)),
            ("check_interval", "Health Check (sec)", self.settings.get("check_interval", 5)),
            ("subnet", "Subnet", self.settings.get("subnet", "192.168.1")),
            ("scan_range_start", "Scan Start", self.settings.get("scan_range_start", 1)),
            ("scan_range_end", "Scan End", self.settings.get("scan_range_end", 254)),
        ]

        entries = {}
        for i, (key, label, default) in enumerate(fields):
            frame = ttk.Frame(scrollable)
            frame.pack(fill="x", padx=20, pady=5)

            ttk.Label(frame, text=label, width=20).pack(side="left")
            entry = ttk.Entry(frame)
            entry.insert(0, str(default))
            entry.pack(side="right", fill="x", expand=True)
            entries[key] = entry

        # Checkboxes
        vars_dict = {}
        for key, label in [
            ("default_screen_off", "Screen Off on Mirror"),
            ("default_power_on_close", "Power Off on Close"),
            ("auto_reconnect", "Auto Reconnect"),
            ("charge_mode", "Charge Mode (1-5 devices)"),
            ("auto_scan", "Auto Scan on Start"),
        ]:
            var = tk.BooleanVar(value=self.settings.get(key, False))
            ttk.Checkbutton(scrollable, text=label, variable=var).pack(padx=20, anchor="w")
            vars_dict[key] = var

        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        # Save button
        def save():
            for key, entry in entries.items():
                val = entry.get()
                if key in ("default_max_size", "grid_per_page", "check_interval", "scan_range_start", "scan_range_end"):
                    try:
                        val = int(val)
                    except ValueError:
                        val = DEFAULTS[key]
                self.settings[key] = val
            for key, var in vars_dict.items():
                self.settings[key] = var.get()
            save_settings(self.settings)
            self.detect_paths()
            dlg.destroy()

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    def cycle_theme(self):
        """Cycle through available themes."""
        themes = ["darkly", "superhero", "cyborg", "solar", "vapor", "lumen", "flatly", "morph"]
        idx = themes.index(self.current_theme) if self.current_theme in themes else 0
        next_theme = themes[(idx + 1) % len(themes)]
        self.apply_theme(next_theme)
        self.refresh_ui()

    # -----------------------------------------------------------------
    # GROUP MANAGEMENT
    # -----------------------------------------------------------------
    def new_group(self):
        """Create a new device group."""
        name = simpledialog.askstring("New Group", "Group name:")
        if name and name.strip() and name.strip() not in self.groups:
            self.groups[name.strip()] = []
            self.group_listbox.insert(tk.END, name.strip())

    def del_group(self):
        """Delete selected group."""
        sel = self.group_listbox.curselection()
        if sel:
            name = self.group_listbox.get(sel[0])
            if name != "All":
                self.groups.pop(name, None)
                self.group_listbox.delete(sel[0])

    # -----------------------------------------------------------------
    # HEALTH CHECK
    # -----------------------------------------------------------------
    def start_health_check(self):
        """Start periodic health check."""
        self.health_running = True
        self._health_check()

    def _health_check(self):
        """Periodically check device status."""
        if not self.health_running:
            return
        self.scan_devices()
        interval = self.settings.get("check_interval", 5) * 1000
        self.root.after(interval, self._health_check)

    # -----------------------------------------------------------------
    # CLEANUP
    # -----------------------------------------------------------------
    def on_close(self):
        """Clean up on app close."""
        self.health_running = False
        self.stop_all_mirrors()
        save_settings(self.settings)
        self.root.destroy()


# =====================================================================
# ENTRY POINT
# =====================================================================
def main():
    if HAS_TTKBOOTSTRAP:
        root = ttkb.Window(themename="darkly", title="Scrcpy Farm v4.0")
    else:
        root = tk.Tk()
        root.title("Scrcpy Farm v4.0")

    ScrcpyFarmApp(root)

if __name__ == "__main__":
    main()
