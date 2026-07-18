#!/usr/bin/env python3
"""
scrcpy-farm v4.0 — Modern UI Android Device Farm Manager
Cross-Platform: Windows, Linux, macOS
Auto-scan, auto-pair, auto-save IPs, grid pagination, broadcast, groups
Modern dark theme with ttkbootstrap

Requirements: Python 3.8+, ttkbootstrap
  pip install ttkbootstrap
Build:
  Windows: pyinstaller --onefile --noconsole scrcpy-farm.py
  Linux:   pyinstaller --onefile scrcpy-farm.py
  macOS:   pyinstaller --onefile --windowed scrcpy-farm.py
"""

import tkinter as tk
import subprocess
import threading
import os
import sys
import json
import time
import re
import platform
import shutil
import urllib.request
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =====================================================================
# MODERN UI — ttkbootstrap (fallback to tkinter)
# =====================================================================
try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
    from ttkbootstrap import Style
    HAS_TTKBOOTSTRAP = True
except ImportError:
    HAS_TTKBOOTSTRAP = False

# tkinter imports (always needed)
try:
    from tkinter import ttk, messagebox, filedialog, simpledialog
except ImportError:
    pass

# =====================================================================
# PLATFORM DETECTION
# =====================================================================
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"

if IS_WINDOWS:
    DEFAULT_SCRCPY = "C:\\scrcpy\\scrcpy.exe"
    DEFAULT_ADB    = "C:\\scrcpy\\adb.exe"
    SCRCPY_DIR     = Path("C:\\scrcpy")
    PING_CMD       = ["ping", "-n", "1", "-w", "200"]
    PING_TIMEOUT   = 2
elif IS_MACOS:
    DEFAULT_SCRCPY = "/opt/homebrew/bin/scrcpy"
    DEFAULT_ADB    = "/opt/homebrew/bin/adb"
    SCRCPY_DIR     = Path.home() / "scrcpy-farm"
    if not Path(DEFAULT_SCRCPY).exists():
        DEFAULT_SCRCPY = "/usr/local/bin/scrcpy"
    if not Path(DEFAULT_ADB).exists():
        DEFAULT_ADB = "/usr/local/bin/adb"
    PING_CMD       = ["ping", "-c", "1", "-W", "2"]
    PING_TIMEOUT   = 3
else:
    DEFAULT_SCRCPY = "/usr/bin/scrcpy"
    DEFAULT_ADB    = "/usr/bin/adb"
    SCRCPY_DIR     = Path.home() / "scrcpy-farm"
    PING_CMD       = ["ping", "-c", "1", "-W", "1"]
    PING_TIMEOUT   = 2

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
# AUTO-DOWNLOAD SCRCPY + ADB
# =====================================================================
class DependencyInstaller:
    """Auto-download and install scrcpy + ADB if missing."""

    @staticmethod
    def get_latest_scrcpy_url():
        """Get latest scrcpy release URL from GitHub."""
        if IS_WINDOWS:
            asset_pattern = re.compile(r"scrcpy-win.*\.zip", re.IGNORECASE)
        elif IS_MACOS:
            asset_pattern = re.compile(r"scrcpy-macos.*\.zip", re.IGNORECASE)
        else:
            asset_pattern = re.compile(r"scrcpy-linux.*\.tar\.gz", re.IGNORECASE)

        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/Genymobile/scrcpy/releases/latest",
                headers={"User-Agent": "scrcpy-farm/4.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                for asset in data.get("assets", []):
                    if asset_pattern.search(asset["name"]):
                        return asset["browser_download_url"], asset["name"]
        except Exception as e:
            print(f"Failed to get latest scrcpy: {e}")
        return None, None

    @staticmethod
    def get_adb_url():
        """Get ADB platform-tools download URL."""
        if IS_WINDOWS:
            return (
                "https://dl.google.com/android/repository/platform-tools_latest_windows.zip",
                "platform-tools",
            )
        elif IS_MACOS:
            return (
                "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
                "platform-tools",
            )
        else:
            return (
                "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
                "platform-tools",
            )

    @staticmethod
    def download_file(url, dest_path, progress_callback=None):
        """Download a file with progress."""
        try:
            def _progress(block_num, block_size, total_size):
                if progress_callback and total_size > 0:
                    pct = min(block_num * block_size / total_size * 100, 100)
                    progress_callback(pct)

            urllib.request.urlretrieve(url, dest_path, _progress)
            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    @classmethod
    def install_all(cls, log_callback=None):
        """Install scrcpy + ADB if missing. Returns dict of paths."""
        def log(msg):
            if log_callback:
                log_callback(msg)
            else:
                print(msg)

        installed = {"scrcpy": None, "adb": None}

        # Create install directory
        if IS_WINDOWS:
            install_dir = Path("C:\\scrcpy")
        else:
            install_dir = Path.home() / ".scrcpy-farm"
        install_dir.mkdir(parents=True, exist_ok=True)

        # Check scrcpy
        scrcpy_name = "scrcpy.exe" if IS_WINDOWS else "scrcpy"
        scrcpy_path = install_dir / scrcpy_name
        if not scrcpy_path.exists():
            log("📦 Downloading scrcpy...")
            url, fname = cls.get_latest_scrcpy_url()
            if url:
                tmp = Path(tempfile.gettempdir()) / fname
                if cls.download_file(url, str(tmp), lambda p: log(f"  scrcpy: {p:.0f}%")):
                    log("  Extracting scrcpy...")
                    if fname.endswith(".zip"):
                        with zipfile.ZipFile(str(tmp)) as zf:
                            # scrcpy zip contains a folder like scrcpy-win64/
                            for member in zf.namelist():
                                parts = member.split("/")
                                if len(parts) > 1:
                                    inner = "/".join(parts[1:])
                                    if inner and not inner.endswith("/"):
                                        target = install_dir / inner
                                        target.parent.mkdir(parents=True, exist_ok=True)
                                        with zf.open(member) as src, open(target, "wb") as dst:
                                            dst.write(src.read())
                        # Find scrcpy.exe in extracted files
                        for f in install_dir.rglob(scrcpy_name):
                            if not f == scrcpy_path:
                                shutil.move(str(f), str(scrcpy_path))
                    tmp.unlink(missing_ok=True)
                    installed["scrcpy"] = str(scrcpy_path)
                    log(f"  ✅ scrcpy installed: {scrcpy_path}")
                else:
                    log("  ❌ scrcpy download failed")
            else:
                log("  ❌ Could not find scrcpy release")
        else:
            installed["scrcpy"] = str(scrcpy_path)
            log(f"  ✅ scrcpy found: {scrcpy_path}")

        # Check ADB
        adb_name = "adb.exe" if IS_WINDOWS else "adb"
        adb_path = install_dir / adb_name
        if not adb_path.exists():
            log("📦 Downloading ADB (platform-tools)...")
            url, folder = cls.get_adb_url()
            if url:
                tmp = Path(tempfile.gettempdir()) / "platform-tools.zip"
                if cls.download_file(url, str(tmp), lambda p: log(f"  ADB: {p:.0f}%")):
                    log("  Extracting ADB...")
                    with zipfile.ZipFile(str(tmp)) as zf:
                        for member in zf.namelist():
                            parts = member.split("/")
                            if len(parts) > 1:
                                inner = "/".join(parts[1:])
                                if inner and not inner.endswith("/"):
                                    target = install_dir / inner
                                    target.parent.mkdir(parents=True, exist_ok=True)
                                    with zf.open(member) as src, open(target, "wb") as dst:
                                        dst.write(src.read())
                    tmp.unlink(missing_ok=True)
                    # Verify
                    if adb_path.exists():
                        installed["adb"] = str(adb_path)
                        log(f"  ✅ ADB installed: {adb_path}")
                    else:
                        # Search for it
                        for f in install_dir.rglob(adb_name):
                            installed["adb"] = str(f)
                            log(f"  ✅ ADB found: {f}")
                            break
                else:
                    log("  ❌ ADB download failed")
            else:
                log("  ❌ Could not get ADB URL")
        else:
            installed["adb"] = str(adb_path)
            log(f"  ✅ ADB found: {adb_path}")

        return installed


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

    def __init__(self):
        self.settings = load_settings()
        self.devices = {}
        self.processes = {}
        self.groups = defaultdict(list)
        self.selected = set()
        self.running = True
        self.grid_page = 0
        self.scanning = False
        self.log_entries = []

        # Build root window
        theme = self.settings.get("theme", "darkly")
        if HAS_TTKBOOTSTRAP:
            self.root = ttkb.Window(
                title="scrcpy Farm — Android Device Manager",
                themename=theme,
                size=(1280, 800),
                minsize=(900, 600),
            )
        else:
            self.root = tk.Tk()
            self.root.title("scrcpy Farm — Android Device Manager")
            self.root.geometry("1280x800")
            self.root.minsize(900, 600)
            self.root.configure(bg="#1a1a2e")

        # Try set icon
        try:
            if IS_WINDOWS:
                scrcpy_p = Path(self.settings.get("scrcpy_path", ""))
                if scrcpy_p.exists():
                    self.root.iconbitmap(str(scrcpy_p))
        except Exception:
            pass

        # Detect dependencies
        self.detect_paths()

        # Build UI
        self.build_ui()

        # Auto-scan
        if self.settings.get("auto_scan", True):
            self.run_auto_scan()

        # Health check loop
        self.start_health_check()

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    # -----------------------------------------------------------------
    # DEPENDENCY DETECTION
    # -----------------------------------------------------------------
    def detect_paths(self):
        """Ensure scrcpy and adb are available, auto-download if not."""
        sp = Path(self.settings.get("scrcpy_path", DEFAULT_SCRCPY))
        ap = Path(self.settings.get("adb_path", DEFAULT_ADB))

        needs_download = not sp.exists() or not ap.exists()

        if needs_download:
            self._show_download_dialog()

    def _show_download_dialog(self):
        """Show download dialog and auto-install dependencies."""
        dlg = tk.Toplevel(self.root) if HAS_TTKBOOTSTRAP else tk.Toplevel(self.root)
        dlg.title("Install Dependencies")
        dlg.geometry("480x280")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        if HAS_TTKBOOTSTRAP:
            ttkb.Label(
                dlg, text="📦 Installing Dependencies",
                font=("Segoe UI", 14, "bold"), bootstyle="primary"
            ).pack(pady=(15, 5))

            ttkb.Label(
                dlg, text="scrcpy and/or ADB not found.\nAuto-downloading from official sources...",
                bootstyle="info", wraplength=420, justify="center"
            ).pack(pady=5)

            log_frame = ttkb.Frame(dlg)
            log_frame.pack(fill="both", expand=True, padx=20, pady=10)

            log_text = tk.Text(log_frame, height=8, font=("Consolas", 9), bg="#0d1117", fg="#00ff41", bd=0)
            log_text.pack(fill="both", expand=True)
            log_text.configure(state="disabled")

            status_var = tk.StringVar(value="Downloading...")
            status_lbl = ttkb.Label(dlg, textvariable=status_var, bootstyle="warning")
            status_lbl.pack(pady=(0, 10))
        else:
            tk.Label(dlg, text="Installing Dependencies", font=("Segoe UI", 14, "bold"), bg="#1a1a2e", fg="white").pack(pady=(15, 5))
            tk.Label(dlg, text="scrcpy and/or ADB not found.\nAuto-downloading...", bg="#1a1a2e", fg="#ccc").pack(pady=5)
            log_frame = tk.Frame(dlg)
            log_frame.pack(fill="both", expand=True, padx=20, pady=10)
            log_text = tk.Text(log_frame, height=8, font=("Consolas", 9), bg="#0d1117", fg="#00ff41", bd=0)
            log_text.pack(fill="both", expand=True)
            log_text.configure(state="disabled")
            status_var = tk.StringVar(value="Downloading...")
            status_lbl = tk.Label(dlg, textvariable=status_var, bg="#1a1a2e", fg="#ffc107")
            status_lbl.pack(pady=(0, 10))

        def log(msg):
            log_text.configure(state="normal")
            log_text.insert(tk.END, msg + "\n")
            log_text.see(tk.END)
            log_text.configure(state="disabled")

        def do_install():
            result = DependencyInstaller.install_all(log_callback=log)
            if result["scrcpy"]:
                self.settings["scrcpy_path"] = result["scrcpy"]
            if result["adb"]:
                self.settings["adb_path"] = result["adb"]
            save_settings(self.settings)
            status_var.set("✅ Done!")
            time.sleep(1)
            dlg.destroy()

        threading.Thread(target=do_install, daemon=True).start()
        self.root.wait_window(dlg)

    # -----------------------------------------------------------------
    # UI BUILD
    # -----------------------------------------------------------------
    def build_ui(self):
        """Build the complete modern UI."""
        # ── Header Bar ──
        if HAS_TTKBOOTSTRAP:
            header = ttkb.Frame(self.root, bootstyle="dark", padding=8)
        else:
            header = tk.Frame(self.root, bg="#16213e", padx=8, pady=8)
        header.pack(fill=tk.X)

        platform_icon = "🖥️" if IS_WINDOWS else ("🍎" if IS_MACOS else "🐧")
        if HAS_TTKBOOTSTRAP:
            ttkb.Label(
                header, text=f"📱 scrcpy Farm v4.0  {platform_icon} {platform.system()}",
                font=("Segoe UI", 16, "bold"), bootstyle="inverse-primary"
            ).pack(side=tk.LEFT)
        else:
            tk.Label(
                header, text=f"📱 scrcpy Farm v4.0  {platform_icon} {platform.system()}",
                font=("Segoe UI", 16, "bold"), bg="#16213e", fg="#e94560"
            ).pack(side=tk.LEFT)

        # Header buttons
        if HAS_TTKBOOTSTRAP:
            ttkb.Button(header, text="⚙ Settings", bootstyle="secondary-outline", command=self.open_settings).pack(side=tk.RIGHT, padx=3)
            ttkb.Button(header, text="▶ Start All", bootstyle="success-outline", command=self.start_all).pack(side=tk.RIGHT, padx=3)
            ttkb.Button(header, text="⏹ Stop All", bootstyle="danger-outline", command=self.stop_all).pack(side=tk.RIGHT, padx=3)
            ttkb.Button(header, text="🔄 Scan", bootstyle="info-outline", command=self.run_auto_scan).pack(side=tk.RIGHT, padx=3)
        else:
            tk.Button(header, text="⚙ Settings", command=self.open_settings, bg="#0f3460", fg="white", bd=0, padx=8, pady=3).pack(side=tk.RIGHT, padx=3)
            tk.Button(header, text="▶ Start All", command=self.start_all, bg="#2ecc71", fg="white", bd=0, padx=8, pady=3).pack(side=tk.RIGHT, padx=3)
            tk.Button(header, text="⏹ Stop All", command=self.stop_all, bg="#e74c3c", fg="white", bd=0, padx=8, pady=3).pack(side=tk.RIGHT, padx=3)

        # ── Stats Bar ──
        if HAS_TTKBOOTSTRAP:
            stats_frame = ttkb.Frame(self.root, padding=5)
        else:
            stats_frame = tk.Frame(self.root, bg="#1a1a2e", padx=5, pady=5)
        stats_frame.pack(fill=tk.X)

        self.stat_labels = {}
        for label, color in [("Total", "#3498db"), ("Online", "#2ecc71"), ("Offline", "#e74c3c"), ("Mirroring", "#f39c12"), ("Known IPs", "#9b59b6")]:
            if HAS_TTKBOOTSTRAP:
                card = ttkb.Frame(stats_frame, bootstyle="dark", padding=4)
                card.pack(side=tk.LEFT, padx=4, fill="x", expand=True)
                ttkb.Label(card, text=label, font=("Segoe UI", 8), bootstyle="secondary").pack()
                val_lbl = ttkb.Label(card, text="0", font=("Segoe UI", 18, "bold"), bootstyle="inverse-dark")
                val_lbl.pack()
            else:
                card = tk.Frame(stats_frame, bg=color, padx=8, pady=4, bd=0)
                card.pack(side=tk.LEFT, padx=3, fill="x", expand=True)
                tk.Label(card, text=label, bg=color, fg="white", font=("Segoe UI", 8)).pack()
                val_lbl = tk.Label(card, text="0", bg=color, fg="white", font=("Segoe UI", 18, "bold"))
                val_lbl.pack()
            self.stat_labels[label] = val_lbl

        # ── Notebook Tabs ──
        if HAS_TTKBOOTSTRAP:
            self.notebook = ttkb.Notebook(self.root, bootstyle="primary")
        else:
            self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        # Tab: Devices
        self.grid_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.grid_tab, text=" 📱 Devices ")
        self._build_grid_tab()

        # Tab: Broadcast
        self.bcast_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.bcast_tab, text=" 📡 Broadcast ")
        self._build_broadcast_tab()

        # Tab: Groups
        self.group_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.group_tab, text=" 📁 Groups ")
        self._build_group_tab()

        # Tab: Monitor
        self.monitor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.monitor_tab, text=" 📊 Monitor ")
        self._build_monitor_tab()

        # ── Status Bar ──
        if HAS_TTKBOOTSTRAP:
            self.status_bar = ttkb.Label(
                self.root, text="✅ Ready", bootstyle="secondary",
                font=("Segoe UI", 8), padding=4
            )
        else:
            self.status_bar = tk.Label(
                self.root, text="✅ Ready", bg="#16213e", fg="#aaa",
                font=("Segoe UI", 8), anchor=tk.W, padx=5
            )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ===================== TAB: DEVICES =====================
    def _build_grid_tab(self):
        # Toolbar
        tb = ttk.Frame(self.grid_tab)
        tb.pack(fill=tk.X, pady=4, padx=4)

        ttk.Button(tb, text="🔄 Refresh", command=self.refresh_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="☑ Select Page", command=self.select_page).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="▶ Start Selected", command=self.start_selected).pack(side=tk.RIGHT, padx=2)
        ttk.Button(tb, text="⏹ Stop Selected", command=self.stop_selected).pack(side=tk.RIGHT, padx=2)

        # Scrollable grid canvas
        cf = tk.Frame(self.grid_tab, bg="#1a1a2e")
        cf.pack(fill="both", expand=True, padx=4)

        self.canvas = tk.Canvas(cf, bg="#0d1117", highlightthickness=0, bd=0)
        sy = ttk.Scrollbar(cf, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sy.set)
        sy.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.grid_inner = tk.Frame(self.canvas, bg="#0d1117")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_inner, anchor="nw")

        self.grid_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Mouse wheel
        def _on_wheel(event):
            if IS_WINDOWS or IS_MACOS:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                self.canvas.yview_scroll(int(-1 * (event.delta)), "units")
        self.canvas.bind("<MouseWheel>", _on_wheel)
        if IS_LINUX:
            self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
            self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # Pagination bar
        pg = ttk.Frame(self.grid_tab)
        pg.pack(fill="x", padx=4, pady=4)
        ttk.Button(pg, text="◀", command=self.page_prev, width=4).pack(side="left")
        self.page_label = ttk.Label(pg, text="Page 0/0", font=("Segoe UI", 10, "bold"))
        self.page_label.pack(side="left", padx=10)
        ttk.Button(pg, text="▶", command=self.page_next, width=4).pack(side="left")
        self.grid_info = ttk.Label(pg, text="", font=("Segoe UI", 8))
        self.grid_info.pack(side="right", padx=10)

    def rebuild_grid(self):
        """Rebuild device cards for current page."""
        for w in self.grid_inner.winfo_children():
            w.destroy()

        device_list = sorted(self.devices.keys())
        per_page = self.settings.get("grid_per_page", 20)
        total_pages = max(1, (len(device_list) + per_page - 1) // per_page)
        if self.grid_page >= total_pages:
            self.grid_page = max(0, total_pages - 1)

        start = self.grid_page * per_page
        page_devices = device_list[start:start + per_page]

        cols = min(5, per_page)
        for i, serial in enumerate(page_devices):
            info = self.devices.get(serial, {})
            card = self._build_device_card(serial, info)
            card.grid(row=i // cols, column=i % cols, padx=4, pady=4, sticky="nsew")

        # Configure grid weights
        for c in range(cols):
            self.grid_inner.columnconfigure(c, weight=1)

        self.page_label.config(text=f"Page {self.grid_page + 1}/{total_pages}")
        self.grid_info.config(text=f"{len(page_devices)} shown · {len(self.devices)} total")
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.update_stats()

    def _build_device_card(self, serial, info):
        """Build a single device card."""
        model = info.get("model", "Unknown")[:20]
        status = info.get("status", "offline")
        battery = info.get("battery", "?%")
        android = info.get("android", "?")
        ip = info.get("ip", "-")
        mirror = info.get("mirror", False)

        # Card colors by status
        if mirror:
            bg, accent, status_color = "#2d1b00", "#f39c12", "#f39c12"
        elif status == "online":
            bg, accent, status_color = "#0d2818", "#2ecc71", "#2ecc71"
        else:
            bg, accent, status_color = "#1a0d0d", "#e74c3c", "#e74c3c"

        if HAS_TTKBOOTSTRAP:
            card = ttkb.Frame(self.grid_inner, bootstyle="dark", padding=0)
        else:
            card = tk.Frame(self.grid_inner, bg=bg, bd=0, highlightthickness=1, highlightbackground=accent)

        card.configure(width=220, height=170)
        card.pack_propagate(False)

        # ── Header ──
        hdr = tk.Frame(card, bg=accent, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  {model}", bg=accent, fg="white", font=("Segoe UI", 9, "bold"), anchor="w").pack(side="left", fill="x", expand=True)

        # ── Body ──
        body = tk.Frame(card, bg=bg, padx=6, pady=4)
        body.pack(fill="both", expand=True)

        # Status row
        r1 = tk.Frame(body, bg=bg)
        r1.pack(fill="x")
        tk.Label(r1, text=f"● {status.upper()}", bg=bg, fg=status_color, font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Label(r1, text=f"🔋 {battery}", bg=bg, fg="#ccc", font=("Segoe UI", 7)).pack(side="right")

        # Info rows
        tk.Label(body, text=f"🤖 Android {android}", bg=bg, fg="#aaa", font=("Segoe UI", 7), anchor="w").pack(fill="x")
        tk.Label(body, text=f"🌐 {ip}", bg=bg, fg="#888", font=("Consolas", 7), anchor="w").pack(fill="x")
        tk.Label(body, text=serial[:28], bg=bg, fg="#555", font=("Consolas", 6), anchor="w").pack(fill="x")

        # ── Buttons ──
        bt = tk.Frame(card, bg=bg, padx=4, pady=3)
        bt.pack(fill="x", side="bottom")

        btn_color = "#e74c3c" if mirror else "#2ecc71"
        btn_text = "⏹" if mirror else "▶"
        cmd = lambda s=serial: self.stop_mirror(s) if mirror else self.start_mirror(s)
        tk.Button(bt, text=btn_text, bg=btn_color, fg="white", bd=0, width=4,
                  font=("Segoe UI", 9, "bold"), command=cmd, cursor="hand2").pack(side="left", padx=1)

        sv = tk.BooleanVar(value=serial in self.selected)
        tk.Checkbutton(bt, text="☐", variable=sv, bg=bg, fg="white",
                       selectcolor=bg, activebackground=bg,
                       command=lambda s=serial, v=sv: self.toggle_sel(s, v.get())).pack(side="right")

        return card

    def page_prev(self):
        if self.grid_page > 0:
            self.grid_page -= 1
            self.rebuild_grid()

    def page_next(self):
        per_page = self.settings.get("grid_per_page", 20)
        total = max(1, (len(self.devices) + per_page - 1) // per_page)
        if self.grid_page < total - 1:
            self.grid_page += 1
            self.rebuild_grid()

    # ===================== TAB: BROADCAST =====================
    def _build_broadcast_tab(self):
        f = ttk.Frame(self.bcast_tab, padding=10)
        f.pack(fill="both", expand=True)

        # Target + options
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))

        ttk.Label(top, text="🎯 Target:", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.btarget = ttk.Combobox(top, values=["All Devices", "Selected Only"], state="readonly", width=20)
        self.btarget.pack(side="left", padx=8)
        self.btarget.set("All Devices")

        ttk.Label(top, text="Delay (s):").pack(side="left")
        self.bdelay = ttk.Spinbox(top, from_=0, to=10, width=5)
        self.bdelay.pack(side="left", padx=4)
        self.bdelay.set(0.3)

        ttk.Button(top, text="▶ Execute", command=self.bcast_run).pack(side="right", padx=4)

        # Command
        cmd_frame = ttk.LabelFrame(f, text="ADB Command", padding=5)
        cmd_frame.pack(fill="x", pady=4)

        self.bcmd = ttk.Entry(cmd_frame, width=100, font=("Consolas", 10))
        self.bcmd.pack(fill="x", pady=2)
        self.bcmd.insert(0, "shell input tap 500 500")

        presets = ttk.Frame(cmd_frame)
        presets.pack(fill="x")
        for txt, cmd in [
            ("Tap", "shell input tap 500 500"),
            ("Swipe", "shell input swipe 100 500 800 500 200"),
            ("Home", "shell input keyevent 3"),
            ("Back", "shell input keyevent 4"),
            ("Power", "shell input keyevent 26"),
            ("Vol+", "shell input keyevent 24"),
            ("Vol-", "shell input keyevent 25"),
            ("Enter", "shell input keyevent 66"),
        ]:
            ttk.Button(presets, text=txt, width=7,
                       command=lambda c=cmd: (self.bcmd.delete(0, tk.END), self.bcmd.insert(0, c))).pack(side="left", padx=1)

        # File upload
        up_frame = ttk.LabelFrame(f, text="📤 Upload APK / File", padding=5)
        up_frame.pack(fill="x", pady=4)

        r1 = ttk.Frame(up_frame)
        r1.pack(fill="x")
        ttk.Label(r1, text="File:").pack(side="left")
        self.up_file = ttk.Entry(r1, width=60)
        self.up_file.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(r1, text="Browse", command=lambda: self._browse_file()).pack(side="right")

        r2 = ttk.Frame(up_frame)
        r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="Dest:").pack(side="left")
        self.up_dest = ttk.Entry(r2, width=60)
        self.up_dest.pack(side="left", padx=5, fill="x", expand=True)
        self.up_dest.insert(0, "/sdcard/")
        ttk.Button(r2, text="📤 Upload All", command=self.bcast_upload).pack(side="right")

        # Log
        log_frame = ttk.LabelFrame(f, text="Output Log", padding=3)
        log_frame.pack(fill="both", expand=True, pady=4)

        self.blog = tk.Text(log_frame, height=12, font=("Consolas", 9), bg="#0d1117", fg="#00ff41", bd=0, insertbackground="#00ff41")
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.blog.yview)
        self.blog.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.blog.pack(fill="both", expand=True)

    def _browse_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.up_file.delete(0, tk.END)
            self.up_file.insert(0, path)

    def _get_targets(self):
        t = self.btarget.get()
        if t == "All Devices":
            return [s for s, d in self.devices.items() if d.get("status") != "offline"]
        elif t == "Selected Only":
            return list(self.selected)
        return []

    def bcast_run(self):
        cmd = self.bcmd.get().strip()
        targets = self._get_targets()
        if not cmd or not targets:
            return
        delay = float(self.bdelay.get() or 0.3)
        self.blog_log(f"📡 Broadcast to {len(targets)} devices: {cmd}")

        def run():
            adb = self.settings.get("adb_path", DEFAULT_ADB)
            for s in targets:
                o = run_cmd([adb, "-s", s] + cmd.split(), timeout=30)
                m = self.devices.get(s, {}).get("model", s)[:15]
                self.blog_log(f"  {m}: {o[:80]}")
                time.sleep(delay)
            self.blog_log("✅ Broadcast complete")

        threading.Thread(target=run, daemon=True).start()

    def bcast_upload(self):
        fp = self.up_file.get().strip()
        dest = self.up_dest.get().strip() or "/sdcard/"
        if not fp or not os.path.exists(fp):
            self.blog_log("❌ File not found")
            return
        targets = self._get_targets()
        if not targets:
            return
        self.blog_log(f"📤 Uploading {os.path.basename(fp)} to {len(targets)} devices...")

        def run():
            adb = self.settings.get("adb_path", DEFAULT_ADB)
            for s in targets:
                o = run_cmd([adb, "-s", s, "push", fp, dest], timeout=60)
                m = self.devices.get(s, {}).get("model", s)[:15]
                self.blog_log(f"  {m}: {o[:60]}")
            self.blog_log("✅ Upload complete")

        threading.Thread(target=run, daemon=True).start()

    def blog_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.blog.insert(tk.END, f"[{ts}] {msg}\n")
        self.blog.see(tk.END)

    # ===================== TAB: GROUPS =====================
    def _build_group_tab(self):
        f = ttk.Frame(self.group_tab, padding=10)
        f.pack(fill="both", expand=True)

        left = ttk.Frame(f)
        left.pack(side="left", fill="y", padx=5)
        ttk.Label(left, text="Groups", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.glist = tk.Listbox(left, height=15, width=18, bg="#0d1117", fg="#00ff41", bd=0, font=("Consolas", 9))
        self.glist.pack(fill="y", expand=True, pady=4)
        self.glist.bind("<<ListboxSelect>>", lambda e: self._refresh_group_members())
        ttk.Button(left, text="+ New", command=self._new_group).pack(fill="x", pady=2)
        ttk.Button(left, text="🗑 Delete", command=self._del_group).pack(fill="x", pady=2)

        right = ttk.Frame(f)
        right.pack(side="right", fill="both", expand=True)

        cols = ttk.Frame(right)
        cols.pack(fill="both", expand=True)

        af = ttk.LabelFrame(cols, text="Available", padding=3)
        af.pack(side="left", fill="both", expand=True, padx=2)
        self.avail = tk.Listbox(af, font=("Consolas", 8), bg="#0d1117", fg="#ccc", bd=0)
        self.avail.pack(fill="both", expand=True)

        mf = ttk.Frame(cols)
        mf.pack(side="left", fill="y", padx=8)
        ttk.Button(mf, text=">>", width=4, command=self._add_to_group).pack(pady=4)
        ttk.Button(mf, text="<<", width=4, command=self._rm_from_group).pack(pady=4)

        gf = ttk.LabelFrame(cols, text="In Group", padding=3)
        gf.pack(side="right", fill="both", expand=True, padx=2)
        self.gdevs = tk.Listbox(gf, font=("Consolas", 8), bg="#0d1117", fg="#2ecc71", bd=0)
        self.gdevs.pack(fill="both", expand=True)

    def _new_group(self):
        n = simpledialog.askstring("New Group", "Group name:")
        if n and n.strip() and n.strip() not in self.groups:
            self.groups[n.strip()] = []

    def _del_group(self):
        sel = self.glist.curselection()
        if sel:
            n = self.glist.get(sel[0])
            self.groups.pop(n, None)

    def _add_to_group(self):
        sel = self.glist.curselection()
        if not sel:
            return
        g = self.glist.get(sel[0])
        for i in self.avail.curselection():
            d = self.avail.get(i).split("  ")[0]
            if d not in self.groups[g]:
                self.groups[g].append(d)
        self._refresh_group_members()

    def _rm_from_group(self):
        sel = self.glist.curselection()
        if not sel:
            return
        g = self.glist.get(sel[0])
        for i in reversed(self.gdevs.curselection()):
            d = self.gdevs.get(i)
            if d in self.groups[g]:
                self.groups[g].remove(d)
        self._refresh_group_members()

    def _refresh_group_members(self):
        self.avail.delete(0, tk.END)
        self.gdevs.delete(0, tk.END)
        sel = self.glist.curselection()
        if not sel:
            return
        g = self.glist.get(sel[0])
        for d, info in self.devices.items():
            if d in self.groups.get(g, []):
                self.gdevs.insert(tk.END, d)
            else:
                self.avail.insert(tk.END, f"{d}  ({info.get('model', '?')[:15]})")

    # ===================== TAB: MONITOR =====================
    def _build_monitor_tab(self):
        f = ttk.Frame(self.monitor_tab, padding=10)
        f.pack(fill="both", expand=True)

        lf = ttk.LabelFrame(f, text="System Log", padding=3)
        lf.pack(fill="both", expand=True)

        tb = ttk.Frame(lf)
        tb.pack(fill="x")
        ttk.Button(tb, text="Clear", command=lambda: self.hlog.delete(1.0, tk.END)).pack(side="right")
        ttk.Button(tb, text="Export", command=self._export_log).pack(side="right", padx=4)
        self.scan_status = ttk.Label(tb, text="Idle", font=("Segoe UI", 8), foreground="#888")
        self.scan_status.pack(side="left")

        self.hlog = tk.Text(lf, height=20, font=("Consolas", 9), bg="#0d1117", fg="#00ff41", bd=0, insertbackground="#00ff41")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.hlog.yview)
        self.hlog.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.hlog.pack(fill="both", expand=True)

    def _export_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if path:
            with open(path, "w") as f:
                f.write(self.hlog.get(1.0, tk.END))

    def hlog_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.hlog.insert(tk.END, f"[{ts}] {msg}\n")
        self.hlog.see(tk.END)

    # ===================== ADB OPERATIONS =====================
    def adb(self, args, timeout=15):
        adb = self.settings.get("adb_path", DEFAULT_ADB)
        if not Path(adb).exists():
            return ""
        return run_cmd([adb] + args.split(), timeout=timeout)

    def adb_list(self, args, timeout=15):
        adb = self.settings.get("adb_path", DEFAULT_ADB)
        if not Path(adb).exists():
            return []
        out = run_cmd([adb] + args.split(), timeout=timeout)
        return [l for l in out.split("\n") if l.strip()]

    def get_devices(self):
        devs = []
        for line in self.adb_list("devices"):
            m = re.match(r"^(\S+)\s+device$", line.strip())
            if m:
                devs.append(m.group(1))
        return devs

    def get_device_info(self, serial):
        info = {
            "serial": serial, "status": "offline", "battery": "?%",
            "android": "?", "ip": "-", "model": "Unknown", "mirror": False,
        }
        state = self.adb(f"-s {serial} get-state")
        if "device" not in state:
            return info
        info["status"] = "online"
        info["model"] = self.adb(f"-s {serial} shell getprop ro.product.model").replace('"', "").strip() or "Unknown"
        info["android"] = self.adb(f"-s {serial} shell getprop ro.build.version.release").strip() or "?"
        bat = self.adb(f"-s {serial} shell dumpsys battery")
        bm = re.search(r"level:\s*(\d+)", bat)
        if bm:
            info["battery"] = f"{bm.group(1)}%"
        route = self.adb(f"-s {serial} shell ip route")
        im = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", route)
        if im:
            info["ip"] = im.group(1)
        if serial in self.processes and self.processes[serial].poll() is None:
            info["mirror"] = True
            info["status"] = "mirror"
        return info

    def connect_device(self, target, port=5555):
        if ":" not in target:
            target = f"{target}:{port}"
        out = self.adb(f"connect {target}", timeout=10)
        ok = "connected" in out.lower()
        self.hlog_log(f"🔌 {target}: {'✅ connected' if ok else f'❌ {out[:40]}'}")
        return ok

    def find_scrcpy(self):
        sp = Path(self.settings.get("scrcpy_path", DEFAULT_SCRCPY))
        if sp.exists():
            return str(sp)
        # Search alternatives
        for alt_name in ["scrcpy.exe", "scrcpy-noconsole.exe", "scrcpy-original.exe", "scrcpy"]:
            candidate = sp.parent / alt_name
            if candidate.exists():
                return str(candidate)
        return None

    # ===================== SCRCPY MIRROR =====================
    def start_mirror(self, serial):
        if serial in self.processes and self.processes[serial].poll() is None:
            return
        exe = self.find_scrcpy()
        if not exe:
            self.hlog_log(f"❌ scrcpy not found! Use Settings to set path or let auto-download handle it.")
            return

        args = [exe, f"--serial={serial}"]
        if self.settings.get("default_screen_off", True):
            args.append("-S")
        if self.settings.get("default_power_on_close", True):
            args.append("--power-off-on-close")
        args.append(f"-m{self.settings.get('default_max_size', 1024)}")
        args.append(f"--bit-rate={self.settings.get('default_bitrate', '4M')}")
        args.append(f"--max-fps={self.settings.get('default_max_fps', 30)}")

        model = self.devices.get(serial, {}).get("model", serial)[:15]
        args.append(f"--window-title={model}")

        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )
            self.processes[serial] = proc
            if serial in self.devices:
                self.devices[serial]["status"] = "mirror"
                self.devices[serial]["mirror"] = True
            self.hlog_log(f"▶ {model}: mirror ON ({self.settings.get('default_max_fps', 30)}fps)")
            self.rebuild_grid()
        except Exception as e:
            self.hlog_log(f"❌ {serial}: {e}")

    def stop_mirror(self, serial):
        if serial in self.processes:
            try:
                p = self.processes[serial]
                if p.poll() is None:
                    if IS_WINDOWS:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                                       capture_output=True, timeout=5)
                    else:
                        p.terminate()
                        p.wait(timeout=3)
            except Exception:
                try:
                    self.processes[serial].kill()
                except Exception:
                    pass
            del self.processes[serial]
        if serial in self.devices:
            self.devices[serial]["status"] = "online"
            self.devices[serial]["mirror"] = False
        self.hlog_log(f"⏹ {serial[:15]}: mirror OFF")
        self.rebuild_grid()

    # ===================== ACTIONS =====================
    def start_all(self):
        for s in list(self.devices.keys()):
            if self.devices[s].get("status") != "offline":
                self.start_mirror(s)

    def stop_all(self):
        for s in list(self.processes.keys()):
            self.stop_mirror(s)

    def start_selected(self):
        for s in list(self.selected):
            self.start_mirror(s)
        self.selected.clear()
        self.rebuild_grid()

    def stop_selected(self):
        for s in list(self.selected):
            self.stop_mirror(s)
        self.selected.clear()
        self.rebuild_grid()

    def select_page(self):
        device_list = sorted(self.devices.keys())
        per_page = self.settings.get("grid_per_page", 20)
        start = self.grid_page * per_page
        for s in device_list[start:start + per_page]:
            self.selected.add(s)
        self.rebuild_grid()

    def toggle_sel(self, serial, state):
        if state:
            self.selected.add(serial)
        else:
            self.selected.discard(serial)

    # ===================== AUTO SCAN =====================
    def run_auto_scan(self):
        """Auto-scan network for Android devices."""
        def scan():
            self.scanning = True
            self.scan_status.config(text="🔄 Scanning...", foreground="#f39c12")

            # Reconnect known IPs first
            known = self.settings.get("known_ips", [])
            if known:
                self.hlog_log(f"🔁 Reconnecting {len(known)} known devices...")
                for ip in known:
                    if ip not in self.devices:
                        self.connect_device(ip)
                        time.sleep(0.3)
                time.sleep(3)
                self.refresh_all()

            # Scan subnet
            subnet = self.settings.get("subnet", "192.168.1")
            start_r = self.settings.get("scan_range_start", 1)
            end_r = self.settings.get("scan_range_end", 254)
            self.hlog_log(f"🔍 Scanning {subnet}.{start_r}-{end_r}...")

            for i in range(start_r, end_r + 1):
                if not self.running:
                    break
                target = f"{subnet}.{i}"
                if target in self.devices or any(target in s for s in self.devices):
                    continue
                try:
                    r = subprocess.run(PING_CMD + [target], capture_output=True, timeout=PING_TIMEOUT)
                    if r.returncode != 0:
                        continue
                except Exception:
                    continue

                ok = self.connect_device(target)
                if ok:
                    known = self.settings.get("known_ips", [])
                    if target not in known:
                        known.append(target)
                        self.settings["known_ips"] = known
                        save_settings(self.settings)

                time.sleep(0.3)
                if i % 20 == 0:
                    self.refresh_all()

            self.scanning = False
            self.refresh_all()
            self.scan_status.config(text=f"✅ Done — {len(self.devices)} devices", foreground="#2ecc71")
            self.hlog_log(f"✅ Scan complete. {len(self.devices)} devices. {len(self.settings.get('known_ips', []))} IPs saved.")

        threading.Thread(target=scan, daemon=True).start()

    def refresh_all(self):
        """Refresh all device states from ADB."""
        adb_devs = self.get_devices()

        for serial in adb_devs:
            if serial not in self.devices:
                self.devices[serial] = self.get_device_info(serial)

        # Remove dead USB devices
        dead = [s for s in self.devices if ":" not in s and s not in adb_devs]
        for s in dead:
            if s in self.processes:
                self.stop_mirror(s)
            del self.devices[s]

        # Update existing
        for serial in list(self.devices.keys()):
            if serial in adb_devs:
                if serial not in self.processes or self.processes[serial].poll() is not None:
                    if not (self.devices[serial].get("mirror") and serial in self.processes):
                        self.devices[serial] = self.get_device_info(serial)
            elif ":" in serial:
                self.devices[serial]["status"] = "offline"

        self.rebuild_grid()

    def update_stats(self):
        total = len(self.devices)
        online = sum(1 for d in self.devices.values() if d.get("status") not in ("offline",))
        offline = total - online
        mirror = sum(1 for d in self.devices.values() if d.get("mirror"))
        known = len(self.settings.get("known_ips", []))

        self.stat_labels["Total"].config(text=str(total))
        self.stat_labels["Online"].config(text=str(online))
        self.stat_labels["Offline"].config(text=str(offline))
        self.stat_labels["Mirroring"].config(text=str(mirror))
        self.stat_labels["Known IPs"].config(text=str(known))

    # ===================== HEALTH CHECK =====================
    def start_health_check(self):
        def loop():
            while self.running:
                try:
                    self.refresh_all()
                except Exception:
                    pass
                time.sleep(self.settings.get("check_interval", 5))
        threading.Thread(target=loop, daemon=True).start()

    # ===================== SETTINGS DIALOG =====================
    def open_settings(self):
        w = tk.Toplevel(self.root)
        w.title("Settings")
        w.geometry("560x650")
        w.resizable(False, False)
        w.transient(self.root)
        w.grab_set()

        r = 0
        ttk.Label(w, text=f"Platform: {platform.system()} {platform.machine()}", foreground="#888").grid(row=r, column=0, columnspan=3, sticky="e", padx=10)
        r += 1

        ttk.Separator(w, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=6)
        r += 1

        ttk.Label(w, text="Paths", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, columnspan=3, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="scrcpy:").grid(row=r, column=0, sticky="w", padx=10, pady=2)
        sp_var = tk.StringVar(value=self.settings.get("scrcpy_path", ""))
        ttk.Entry(w, textvariable=sp_var, width=48).grid(row=r, column=1, columnspan=2, pady=2, padx=10)
        r += 1

        ttk.Label(w, text="adb:").grid(row=r, column=0, sticky="w", padx=10, pady=2)
        ap_var = tk.StringVar(value=self.settings.get("adb_path", ""))
        ttk.Entry(w, textvariable=ap_var, width=48).grid(row=r, column=1, columnspan=2, pady=2, padx=10)
        r += 1

        ttk.Separator(w, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=6)
        r += 1

        ttk.Label(w, text="Mirror", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, columnspan=3, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="Bitrate:").grid(row=r, column=0, sticky="w", padx=10)
        bv = ttk.Combobox(w, values=["1M", "2M", "4M", "8M", "12M", "16M", "32M"], width=10)
        bv.set(self.settings.get("default_bitrate", "4M"))
        bv.grid(row=r, column=1, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="Max Size:").grid(row=r, column=0, sticky="w", padx=10)
        sv = tk.IntVar(value=self.settings.get("default_max_size", 1024))
        ttk.Spinbox(w, from_=240, to=2160, textvariable=sv, width=10).grid(row=r, column=1, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="Max FPS:").grid(row=r, column=0, sticky="w", padx=10)
        fv = tk.IntVar(value=self.settings.get("default_max_fps", 30))
        ttk.Spinbox(w, from_=1, to=240, textvariable=fv, width=10).grid(row=r, column=1, sticky="w", padx=10)
        ttk.Label(w, text="(1-240)", foreground="#888").grid(row=r, column=2, sticky="w")
        r += 1

        sov = tk.BooleanVar(value=self.settings.get("default_screen_off", True))
        ttk.Checkbutton(w, text="Screen Off (-S) when mirroring", variable=sov).grid(row=r, column=0, columnspan=2, sticky="w", padx=10)
        r += 1

        pov = tk.BooleanVar(value=self.settings.get("default_power_on_close", True))
        ttk.Checkbutton(w, text="Power On screen when window closes", variable=pov).grid(row=r, column=0, columnspan=2, sticky="w", padx=10)
        r += 1

        ttk.Separator(w, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=6)
        r += 1

        ttk.Label(w, text="Grid", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, columnspan=3, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="Devices/page:").grid(row=r, column=0, sticky="w", padx=10)
        gpv = tk.IntVar(value=self.settings.get("grid_per_page", 20))
        ttk.Spinbox(w, from_=5, to=100, textvariable=gpv, width=10).grid(row=r, column=1, sticky="w", padx=10)
        r += 1

        ttk.Separator(w, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=6)
        r += 1

        ttk.Label(w, text="Network", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, columnspan=3, sticky="w", padx=10)
        r += 1

        asv = tk.BooleanVar(value=self.settings.get("auto_scan", True))
        ttk.Checkbutton(w, text="Auto-scan subnet on startup", variable=asv).grid(row=r, column=0, columnspan=2, sticky="w", padx=10)
        r += 1

        arv = tk.BooleanVar(value=self.settings.get("auto_reconnect", True))
        ttk.Checkbutton(w, text="Auto-reconnect known devices", variable=arv).grid(row=r, column=0, columnspan=2, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="Subnet:").grid(row=r, column=0, sticky="w", padx=10)
        snv = tk.StringVar(value=self.settings.get("subnet", "192.168.1"))
        ttk.Entry(w, textvariable=snv, width=15).grid(row=r, column=1, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="IP Range:").grid(row=r, column=0, sticky="w", padx=10)
        frmv = tk.IntVar(value=self.settings.get("scan_range_start", 1))
        ttk.Spinbox(w, from_=1, to=254, textvariable=frmv, width=6).grid(row=r, column=1, sticky="w", padx=10)
        ttk.Label(w, text=" to ").grid(row=r, column=1, sticky="e", padx=60)
        tov = tk.IntVar(value=self.settings.get("scan_range_end", 254))
        ttk.Spinbox(w, from_=1, to=254, textvariable=tov, width=6).grid(row=r, column=2, sticky="w")
        r += 1

        ttk.Separator(w, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=6)
        r += 1

        ttk.Label(w, text="Charge", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, columnspan=3, sticky="w", padx=10)
        r += 1

        chv = tk.BooleanVar(value=self.settings.get("charge_mode", False))
        ttk.Checkbutton(w, text="🔋 Disable ADB charging (only works ≤5 devices)", variable=chv).grid(row=r, column=0, columnspan=3, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="Auto-disabled when >5 devices connected.", foreground="#888", font=("Segoe UI", 8)).grid(row=r, column=0, columnspan=3, sticky="w", padx=10)
        r += 1

        ttk.Separator(w, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=6)
        r += 1

        ttk.Label(w, text="Theme", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, columnspan=3, sticky="w", padx=10)
        r += 1

        ttk.Label(w, text="Theme:").grid(row=r, column=0, sticky="w", padx=10)
        themes = ["darkly", "superhero", "cyborg", "solar", "vapor", "lumen", "flatly", "journal", "morph"]
        tv = ttk.Combobox(w, values=themes, state="readonly", width=15)
        tv.set(self.settings.get("theme", "darkly"))
        tv.grid(row=r, column=1, sticky="w", padx=10)
        r += 1

        def save():
            self.settings["scrcpy_path"] = sp_var.get()
            self.settings["adb_path"] = ap_var.get()
            self.settings["default_bitrate"] = bv.get()
            self.settings["default_max_size"] = sv.get()
            self.settings["default_max_fps"] = fv.get()
            self.settings["default_screen_off"] = sov.get()
            self.settings["default_power_on_close"] = pov.get()
            self.settings["grid_per_page"] = gpv.get()
            self.settings["auto_scan"] = asv.get()
            self.settings["auto_reconnect"] = arv.get()
            self.settings["subnet"] = snv.get()
            self.settings["scan_range_start"] = frmv.get()
            self.settings["scan_range_end"] = tov.get()
            self.settings["charge_mode"] = chv.get()
            self.settings["theme"] = tv.get()
            save_settings(self.settings)
            self.rebuild_grid()
            w.destroy()
            self.hlog_log("⚙ Settings saved")

        ttk.Button(w, text="💾 Save & Close", command=save).grid(row=r, column=0, columnspan=3, pady=15)

    # ===================== CLOSE =====================
    def on_close(self):
        self.running = False
        for s in list(self.processes.keys()):
            self.stop_mirror(s)
        # Save known IPs
        ips = set(s for s in self.devices if ":" in s) | set(self.settings.get("known_ips", []))
        self.settings["known_ips"] = sorted(ips)
        save_settings(self.settings)
        self.root.destroy()


# =====================================================================
# ENTRY POINT
# =====================================================================
if __name__ == "__main__":
    app = ScrcpyFarmApp()
