#!/usr/bin/env python3
"""
scrcpy-farm.py — Cross-Platform Multi-Device Android Farm Manager
Supports Windows, Linux, macOS.
Auto-scan network, auto-pair, auto-save IPs, grid pagination, broadcast, groups.

Requirements:
  - scrcpy (https://github.com/Genymobile/scrcpy)
  - adb (Android SDK platform-tools)
  - Python 3.8+ with tkinter

Build:
  Windows: pyinstaller --onefile --noconsole scrcpy-farm.py
  Linux:   pyinstaller --onefile scrcpy-farm.py
  macOS:   pyinstaller --onefile --windowed scrcpy-farm.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import subprocess
import threading
import os
import sys
import json
import time
import re
import platform
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =====================================================================
# PLATFORM DETECTION
# =====================================================================
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"

# =====================================================================
# DEFAULT SETTINGS (per-platform)
# =====================================================================
if IS_WINDOWS:
    DEFAULT_SCRCPY = "C:\\scrcpy\\scrcpy.exe"
    DEFAULT_ADB    = "C:\\scrcpy\\adb.exe"
    PING_CMD       = ["ping", "-n", "1", "-w", "200"]
    PING_TIMEOUT   = 2
    NUL            = "nul"
    SETTINGS_DIR   = Path.home() / ".scrcpy-farm.json"
elif IS_MACOS:
    # Check common brew locations
    DEFAULT_SCRCPY = "/opt/homebrew/bin/scrcpy"
    DEFAULT_ADB    = "/opt/homebrew/bin/adb"
    # Fallback
    if not Path(DEFAULT_SCRCPY).exists():
        DEFAULT_SCRCPY = "/usr/local/bin/scrcpy"
    if not Path(DEFAULT_ADB).exists():
        DEFAULT_ADB = "/usr/local/bin/adb"
    PING_CMD       = ["ping", "-c", "1", "-t", "2"]
    PING_TIMEOUT   = 2
    NUL            = "/dev/null"
    SETTINGS_DIR   = Path.home() / ".scrcpy-farm.json"
else:  # Linux
    DEFAULT_SCRCPY = "/usr/bin/scrcpy"
    DEFAULT_ADB    = "/usr/bin/adb"
    PING_CMD       = ["ping", "-c", "1", "-W", "1"]
    PING_TIMEOUT   = 2
    NUL            = "/dev/null"
    SETTINGS_DIR   = Path.home() / ".scrcpy-farm.json"

DEFAULT = {
    "scrcpy_path": str(DEFAULT_SCRCPY),
    "adb_path": str(DEFAULT_ADB),
    "default_bitrate": "2M",
    "default_max_size": 800,
    "default_max_fps": 10,
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
}


class DeviceFarm:
    """Multi-Device Android Farm Manager — scrcpy GUI."""

    def __init__(self, root):
        self.root = root
        self.root.title("scrcpy Farm — Android Device Manager")
        self.root.geometry("1200x820")

        # Set icon if available
        try:
            if IS_LINUX:
                self.root.iconname("scrcpy-farm")
        except Exception:
            pass

        self.settings = self.load_settings()
        self.devices = {}
        self.processes = {}
        self.groups = defaultdict(list)
        self.device_frames = {}
        self.selected_devices = set()
        self.running = True
        self.grid_page = 0
        self.scanning = False
        self.last_device_count = 0

        # Detect actual scrcpy/adb paths
        self.detect_paths()

        self.setup_ui()
        self.rebuild_grid()

        # Start auto-scan if enabled
        if self.settings.get("auto_scan", True):
            self.start_auto_scan()
        self.start_health_check()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # -----------------------------------------------------------------
    # PATH DETECTION
    # -----------------------------------------------------------------
    def detect_paths(self):
        """Auto-detect scrcpy and adb paths if configured ones don't exist."""
        scrcpy = self.settings.get("scrcpy_path", DEFAULT_SCRCPY)
        adb = self.settings.get("adb_path", DEFAULT_ADB)

        if not Path(scrcpy).exists():
            found = self.which("scrcpy")
            if found:
                self.settings["scrcpy_path"] = found
            elif IS_WINDOWS:
                # Search common locations
                for p in [
                    r"C:\scrcpy\scrcpy.exe",
                    r"C:\scrcpy\scrcpy-noconsole.exe",
                    r"C:\Program Files\scrcpy\scrcpy.exe",
                    str(Path.home() / "scrcpy" / "scrcpy.exe"),
                ]:
                    if Path(p).exists():
                        self.settings["scrcpy_path"] = p
                        break
            self.save_settings()

        if not Path(adb).exists():
            found = self.which("adb")
            if found:
                self.settings["adb_path"] = found
            elif IS_WINDOWS:
                for p in [
                    r"C:\scrcpy\adb.exe",
                    r"C:\Program Files\scrcpy\adb.exe",
                    r"C:\Android\platform-tools\adb.exe",
                ]:
                    if Path(p).exists():
                        self.settings["adb_path"] = p
                        break
            self.save_settings()

    @staticmethod
    def which(cmd):
        """Find executable in PATH."""
        try:
            r = subprocess.run(
                ["where" if IS_WINDOWS else "which", cmd],
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip().split("\n")[0] if r.returncode == 0 else None
        except Exception:
            return None

    # -----------------------------------------------------------------
    # SETTINGS
    # -----------------------------------------------------------------
    def load_settings(self):
        try:
            if SETTINGS_DIR.exists():
                with open(SETTINGS_DIR) as f:
                    s = {**DEFAULT, **json.load(f)}
                    if not isinstance(s.get("known_ips"), list):
                        s["known_ips"] = []
                    return s
        except Exception:
            pass
        return dict(DEFAULT)

    def save_settings(self):
        try:
            with open(SETTINGS_DIR, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def save_known_ips(self):
        """Persist known TCP/IP device list."""
        ips = set(
            s for s in self.devices.keys()
            if ":" in s
        ) | set(self.settings.get("known_ips", []))
        self.settings["known_ips"] = sorted(ips)
        self.save_settings()

    # -----------------------------------------------------------------
    # UI SETUP
    # -----------------------------------------------------------------
    def setup_ui(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="⚙ Settings", command=self.open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="▶ Start All", command=self.start_all)
        tools_menu.add_command(label="⏹ Stop All", command=self.stop_all)
        tools_menu.add_command(label="☑ Select Page", command=self.select_page)
        tools_menu.add_separator()
        tools_menu.add_command(label="Clear Offline", command=self.clear_offline)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        info_menu = tk.Menu(menubar, tearoff=0)
        info_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=info_menu)

        # Notebook tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.grid_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.grid_tab, text="📱 Devices")
        self.build_grid_tab()

        self.bcast_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.bcast_tab, text="📡 Broadcast")
        self.build_broadcast_tab()

        self.group_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.group_tab, text="📁 Groups")
        self.build_group_tab()

        self.monitor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.monitor_tab, text="📊 Monitor")
        self.build_monitor_tab()

        # Status bar
        sf = ttk.Frame(self.root)
        sf.pack(fill=tk.X, side=tk.BOTTOM)
        self.stat_label = ttk.Label(sf, text="Ready")
        self.stat_label.pack(side=tk.LEFT, padx=5)
        self.count_label = ttk.Label(
            sf, text="Devices: 0 | Online: 0 | Mirror: 0 | Page: 0/0"
        )
        self.count_label.pack(side=tk.RIGHT, padx=5)

        @staticmethod
        def get_os_icon():
            """Return OS-specific icon emoji."""
            if IS_WINDOWS:
                return "🪟"
            elif IS_MACOS:
                return "🍎"
            else:
                return "🐧"

    # ===================== TAB 1: GRID =====================
    def build_grid_tab(self):
        tb = ttk.Frame(self.grid_tab)
        tb.pack(fill=tk.X, pady=3, padx=5)

        ttk.Button(tb, text="🔄 Refresh", command=self.rebuild_grid).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb, text="▶ Start All", command=self.start_all).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb, text="⏹ Stop All", command=self.stop_all).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb, text="☑ Select Page", command=self.select_page).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb, text="▶ Start Sel", command=self.start_selected).pack(side=tk.RIGHT, padx=1)
        ttk.Button(tb, text="⏹ Stop Sel", command=self.stop_selected).pack(side=tk.RIGHT, padx=1)
        ttk.Label(tb, text=f"  {platform.system()}").pack(side=tk.RIGHT, padx=5)

        # Canvas with scroll
        cf = ttk.Frame(self.grid_tab)
        cf.pack(fill=tk.BOTH, expand=True, padx=5)

        self.canvas = tk.Canvas(cf, bg="#1a1a2e", highlightthickness=0)
        sy = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sy.set)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.grid_inner = tk.Frame(self.canvas, bg="#1a1a2e")
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.grid_inner, anchor="nw"
        )
        self.grid_inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        # Mouse wheel scroll
        def _on_mousewheel(event):
            if IS_WINDOWS or IS_MACOS:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                self.canvas.yview_scroll(int(-1 * (event.delta)), "units")
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        if IS_LINUX:
            self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
            self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # Pagination
        pg = ttk.Frame(self.grid_tab)
        pg.pack(fill=tk.X, pady=3, padx=5)

        ttk.Button(pg, text="◀ Prev", command=self.page_prev).pack(side=tk.LEFT, padx=2)
        self.page_label = ttk.Label(pg, text="Page 0/0", font=("Segoe UI", 9, "bold"))
        self.page_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(pg, text="Next ▶", command=self.page_next).pack(side=tk.LEFT, padx=2)
        self.grid_count_label = ttk.Label(pg, text="")
        self.grid_count_label.pack(side=tk.RIGHT, padx=10)

    def rebuild_grid(self):
        """Rebuild the current grid page."""
        for w in self.grid_inner.winfo_children():
            w.destroy()

        device_list = sorted(self.devices.keys())
        per_page = self.settings.get("grid_per_page", 20)
        total_pages = max(1, (len(device_list) + per_page - 1) // per_page)
        if self.grid_page >= total_pages:
            self.grid_page = max(0, total_pages - 1)

        start = self.grid_page * per_page
        end = start + per_page
        page_devices = device_list[start:end]

        cols = min(5, per_page)
        for i, serial in enumerate(page_devices):
            info = self.devices.get(serial, {})
            f = self.build_card(serial, info)
            f.grid(row=i // cols, column=i % cols, padx=3, pady=3, sticky="nsew")

        self.page_label.config(text=f"Page {self.grid_page + 1}/{total_pages}")
        self.grid_count_label.config(
            text=f"{len(page_devices)} shown | {len(self.devices)} total"
        )
        self.update_status_bar()
        self.grid_inner.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def build_card(self, serial, info):
        """Build a device card widget."""
        model = info.get("model", "Unknown")[:18]
        status = info.get("status", "offline")
        battery = info.get("battery", "?%")
        android = info.get("android", "?")
        ip = info.get("ip", "-")
        mirror = info.get("mirror", False)

        frame = tk.Frame(
            self.grid_inner, bg="#16213e", bd=1, relief=tk.RAISED,
            width=210, height=155,
        )
        frame.pack_propagate(False)

        # Header
        hdr = tk.Frame(frame, bg="#0f3460")
        hdr.pack(fill=tk.X)
        tk.Label(
            hdr, text=model, bg="#0f3460", fg="white",
            font=("Segoe UI", 8, "bold"), anchor=tk.W
        ).pack(padx=4, pady=1, fill=tk.X)

        # Body
        body = tk.Frame(frame, bg="#16213e")
        body.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        r1 = tk.Frame(body, bg="#16213e")
        r1.pack(fill=tk.X)
        sc = {"online": "#4ecca3", "offline": "#e23e57", "mirror": "#ffc107"}.get(
            status, "#aaa"
        )
        tk.Label(
            r1, text=f"● {status}", bg="#16213e", fg=sc,
            font=("Segoe UI", 7, "bold")
        ).pack(side=tk.LEFT)
        tk.Label(
            r1, text=f"🔋 {battery}", bg="#16213e", fg="white",
            font=("Segoe UI", 7)
        ).pack(side=tk.RIGHT)

        tk.Label(
            body, text=f"🤖 {android}", bg="#16213e", fg="#ccc",
            font=("Segoe UI", 7), anchor=tk.W
        ).pack(fill=tk.X)
        tk.Label(
            body, text=f"🌐 {ip}", bg="#16213e", fg="#999",
            font=("Consolas", 7), anchor=tk.W
        ).pack(fill=tk.X)

        s = serial[:28]
        tk.Label(
            body, text=s, bg="#16213e", fg="#666",
            font=("Consolas", 6), anchor=tk.W
        ).pack(fill=tk.X)

        # Buttons
        bt = tk.Frame(frame, bg="#16213e")
        bt.pack(fill=tk.X, padx=4, pady=2, side=tk.BOTTOM)

        if mirror:
            tk.Button(
                bt, text="⏹", bg="#e23e57", fg="white", bd=0,
                command=lambda s=serial: self.stop_mirror(s), width=4,
            ).pack(side=tk.LEFT, padx=1)
        else:
            tk.Button(
                bt, text="▶", bg="#4ecca3", fg="white", bd=0,
                command=lambda s=serial: self.start_mirror(s), width=4,
            ).pack(side=tk.LEFT, padx=1)

        sv = tk.BooleanVar(value=serial in self.selected_devices)
        tk.Checkbutton(
            bt, text="✓", variable=sv, bg="#16213e", fg="white",
            command=lambda s=serial, v=sv: self.toggle_sel(s, v.get()),
        ).pack(side=tk.RIGHT)

        return frame

    def page_prev(self):
        if self.grid_page > 0:
            self.grid_page -= 1
            self.rebuild_grid()

    def page_next(self):
        device_list = sorted(self.devices.keys())
        per_page = self.settings.get("grid_per_page", 20)
        total = max(1, (len(device_list) + per_page - 1) // per_page)
        if self.grid_page < total - 1:
            self.grid_page += 1
            self.rebuild_grid()

    # ===================== ADB HELPERS =====================
    def adb(self, cmd, timeout=15):
        """Run ADB command and return stdout."""
        try:
            adb = self.settings.get("adb_path", DEFAULT_ADB)
            if not Path(adb).exists():
                return ""
            r = subprocess.run(
                [adb] + cmd.split(),
                capture_output=True, text=True, timeout=timeout,
            )
            return r.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except Exception:
            return ""

    def get_devices(self):
        """List connected ADB devices."""
        out = self.adb("devices")
        devs = []
        for line in out.split("\n"):
            m = re.match(r"^(\S+)\s+device$", line.strip())
            if m:
                devs.append(m.group(1))
        return devs

    def get_info(self, serial):
        """Get device information."""
        info = {
            "serial": serial,
            "status": "offline",
            "battery": "?%",
            "android": "?",
            "ip": "-",
            "model": "Unknown",
            "mirror": False,
        }

        state = self.adb(f"-s {serial} get-state")
        if "device" not in state:
            return info

        info["status"] = "online"

        m = self.adb(f"-s {serial} shell getprop ro.product.model")
        info["model"] = m.strip().replace('"', "") or "Unknown"

        av = self.adb(f"-s {serial} shell getprop ro.build.version.release")
        info["android"] = av.strip() or "?"

        bat = self.adb(f"-s {serial} shell dumpsys battery")
        bm = re.search(r"level:\s*(\d+)", bat)
        info["battery"] = f"{bm.group(1)}%" if bm else "?"

        ip = self.adb(f"-s {serial} shell ip route")
        im = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", ip)
        info["ip"] = im.group(1) if im else "-"

        if serial in self.processes and self.processes[serial].poll() is None:
            info["mirror"] = True
            info["status"] = "mirror"

        return info

    def connect(self, target, port=5555):
        """Connect to device via TCP/IP."""
        if ":" not in target:
            target = f"{target}:{port}"
        out = self.adb(f"connect {target}", timeout=10)
        ok = "connected" in out.lower()
        self.log(f"🔌 Connect {target}: {'✅' if ok else '❌'} {out[:60]}")
        return ok

    def disable_charging(self, serial):
        """Disable battery charging via ADB (for USB power saving)."""
        try:
            self.adb(f"-s {serial} shell dumpsys battery set status 1", timeout=5)
            self.log(f"🔋 Charging disabled: {serial}")
        except Exception:
            pass

    # ===================== SCRCPY =====================
    def find_scrcpy(self):
        """Find scrcpy binary."""
        sp = self.settings.get("scrcpy_path", DEFAULT_SCRCPY)
        if Path(sp).exists():
            return sp

        # Search alternatives
        alternatives = []
        if IS_WINDOWS:
            base = os.path.dirname(sp)
            alternatives = [
                os.path.join(base, "scrcpy-noconsole.exe"),
                os.path.join(base, "scrcpy-original.exe"),
            ]
        for alt in alternatives:
            if Path(alt).exists():
                return alt
        return None

    def start_mirror(self, serial):
        """Start scrcpy mirroring for a device."""
        if serial in self.processes and self.processes[serial].poll() is None:
            return

        exe = self.find_scrcpy()
        if not exe:
            self.log(f"❌ scrcpy not found! Install scrcpy first.")
            return

        args = [exe, f"--serial={serial}"]

        if self.settings.get("default_screen_off", True):
            args.append("-S")
        if self.settings.get("default_power_on_close", True):
            args.append("--power-off-on-close")

        args.append(f'-m{self.settings.get("default_max_size", 800)}')
        args.append(f'--bit-rate={self.settings.get("default_bitrate", "2M")}')
        args.append(f'--max-fps={self.settings.get("default_max_fps", 10)}')

        model = self.devices.get(serial, {}).get("model", serial)[:15]
        args.append(f"--window-title={model}")

        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.processes[serial] = proc
            if serial in self.devices:
                self.devices[serial]["status"] = "mirror"
                self.devices[serial]["mirror"] = True
            self.log(f"▶ {model}: mirror started")
            self.rebuild_grid()
        except Exception as e:
            self.log(f"❌ {serial}: {e}")

    def stop_mirror(self, serial):
        """Stop scrcpy mirroring for a device."""
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
        self.log(f"⏹ Mirror stopped: {serial}")
        self.rebuild_grid()

    # ===================== AUTO SCAN + PAIR =====================
    def start_auto_scan(self):
        """Background network scanner."""
        def scan():
            subnet = self.settings.get("subnet", "192.168.1")
            start_r = self.settings.get("scan_range_start", 1)
            end_r = self.settings.get("scan_range_end", 254)

            # Reconnect known IPs first
            known = self.settings.get("known_ips", [])
            if known:
                self.log(f"🔁 Reconnecting {len(known)} known devices...")
                for ip in known:
                    if ip not in self.devices:
                        self.connect(ip)
                        time.sleep(0.3)
                time.sleep(3)
                self.refresh_all()

            # Then scan subnet for new devices
            self.scanning = True
            self.log(f"🔍 Scanning {subnet}.{start_r}-{end_r} for new devices...")

            for i in range(start_r, end_r + 1):
                if not self.running:
                    break
                target = f"{subnet}.{i}"

                # Skip already connected
                if target in self.devices or any(
                    target in s for s in self.devices
                ):
                    continue

                # Quick ping test
                try:
                    r = subprocess.run(
                        PING_CMD + [target],
                        capture_output=True, timeout=PING_TIMEOUT,
                    )
                    if r.returncode != 0:
                        continue
                except Exception:
                    continue

                # Host up — try ADB connect
                self.log(f"  📡 Host up: {target} → connecting...")
                ok = self.connect(target)
                if ok:
                    known = self.settings.get("known_ips", [])
                    if target not in known:
                        known.append(target)
                        self.settings["known_ips"] = known
                        self.save_settings()

                # Rate limit
                time.sleep(0.5)

                if i % 20 == 0:
                    self.refresh_all()

            self.scanning = False
            self.refresh_all()
            kc = len(self.settings.get("known_ips", []))
            self.log(
                f"✅ Scan complete. {len(self.devices)} device(s) online. "
                f"{kc} IPs saved."
            )
            self.update_charge_mode()

        t = threading.Thread(target=scan, daemon=True)
        t.start()

    def start_health_check(self):
        """Periodic health check."""
        def loop():
            while self.running:
                try:
                    self.refresh_all()
                    self.update_charge_mode()
                except Exception:
                    pass
                time.sleep(self.settings.get("check_interval", 5))

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def refresh_all(self):
        """Refresh all device info from ADB."""
        adb_devs = self.get_devices()

        # Add new devices
        for serial in adb_devs:
            if serial not in self.devices:
                info = self.get_info(serial)
                self.devices[serial] = info

        # Remove dead USB devices (keep TCP/IP)
        dead = [s for s in self.devices if ":" not in s and s not in adb_devs]
        for s in dead:
            if s in self.processes:
                self.stop_mirror(s)
            del self.devices[s]

        # Update status for existing
        for serial in list(self.devices.keys()):
            if serial in adb_devs:
                if serial not in self.processes or self.processes[serial].poll() is not None:
                    if not (self.devices[serial]["mirror"] and serial not in self.processes):
                        info = self.get_info(serial)
                        self.devices[serial] = info
            elif ":" in serial:
                # TCP/IP missing — mark offline
                self.devices[serial]["status"] = "offline"

        self.rebuild_grid()
        self.update_status_bar()

    def update_charge_mode(self):
        """Auto-toggle charge mode based on device count."""
        online = sum(
            1 for d in self.devices.values() if d.get("status") != "offline"
        )
        charge = self.settings.get("charge_mode", False)

        if online <= 5 and charge:
            for serial in self.devices:
                if self.devices[serial].get("status") != "offline":
                    self.disable_charging(serial)
        elif online > 5 and charge:
            self.settings["charge_mode"] = False
            self.log("⚡ Charge mode disabled (>5 devices connected)")
            self.save_settings()

    # ===================== COMMANDS =====================
    def start_all(self):
        for s in list(self.devices.keys()):
            if self.devices[s].get("status") != "offline":
                self.start_mirror(s)
        self.rebuild_grid()

    def stop_all(self):
        for s in list(self.processes.keys()):
            self.stop_mirror(s)
        self.rebuild_grid()

    def select_page(self):
        device_list = sorted(self.devices.keys())
        per_page = self.settings.get("grid_per_page", 20)
        start = self.grid_page * per_page
        end = start + per_page
        for s in device_list[start:end]:
            self.selected_devices.add(s)
        self.rebuild_grid()

    def toggle_sel(self, serial, state):
        if state:
            self.selected_devices.add(serial)
        else:
            self.selected_devices.discard(serial)

    def start_selected(self):
        for s in list(self.selected_devices):
            self.start_mirror(s)
        self.selected_devices.clear()
        self.rebuild_grid()

    def stop_selected(self):
        for s in list(self.selected_devices):
            self.stop_mirror(s)
        self.selected_devices.clear()
        self.rebuild_grid()

    def clear_offline(self):
        dead = [s for s in self.devices if self.devices[s].get("status") == "offline"]
        for s in dead:
            if s in self.processes:
                self.stop_mirror(s)
            del self.devices[s]
        self.rebuild_grid()

    def update_status_bar(self):
        total = len(self.devices)
        online = sum(1 for d in self.devices.values() if d.get("status") != "offline")
        mirror = len(self.processes)
        device_list = sorted(self.devices.keys())
        per_page = self.settings.get("grid_per_page", 20)
        total_pages = max(1, (len(device_list) + per_page - 1) // per_page)
        self.count_label.config(
            text=f"Devices: {total} | Online: {online} | Mirror: {mirror} "
                 f"| Page {self.grid_page + 1}/{total_pages}"
        )
        self.stat_label.config(
            text=f"{datetime.now().strftime('%H:%M:%S')} "
                 f"{'🔄 Scanning' if self.scanning else '● Idle'} "
                 f"| {platform.system()}"
        )

    # ===================== BROADCAST =====================
    def build_broadcast_tab(self):
        f = ttk.Frame(self.bcast_tab, padding=10)
        f.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(f)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Target:").pack(side=tk.LEFT)
        self.btarget = ttk.Combobox(
            top, values=["All Devices", "Selected Only"],
            state="readonly", width=25,
        )
        self.btarget.pack(side=tk.LEFT, padx=5)
        self.btarget.set("All Devices")

        ttk.Label(top, text="Delay (s):").pack(side=tk.LEFT)
        self.bdelay = ttk.Spinbox(top, from_=0, to=10, width=5)
        self.bdelay.pack(side=tk.LEFT, padx=2)
        self.bdelay.set(0.3)

        ttk.Button(top, text="▶ Execute", command=self.bcast_run).pack(
            side=tk.RIGHT, padx=5
        )

        # Command entry
        cmd_f = ttk.LabelFrame(f, text="ADB Command", padding=5)
        cmd_f.pack(fill=tk.X, pady=5)

        self.bcmd = ttk.Entry(cmd_f, width=100, font=("Consolas", 10))
        self.bcmd.pack(fill=tk.X, pady=2)
        self.bcmd.insert(0, "shell input tap 500 500")

        presets_f = ttk.Frame(cmd_f)
        presets_f.pack(fill=tk.X)
        for txt, cmd in [
            ("Tap center", "shell input tap 500 500"),
            ("Swipe right", "shell input swipe 100 500 800 500 200"),
            ("Home", "shell input keyevent 3"),
            ("Back", "shell input keyevent 4"),
            ("Power", "shell input keyevent 26"),
            ("Vol Up", "shell input keyevent 24"),
            ("Vol Down", "shell input keyevent 25"),
            ("Enter", "shell input keyevent 66"),
        ]:
            ttk.Button(
                presets_f, text=txt, width=10,
                command=lambda c=cmd: self.bcmd.delete(0, tk.END) or self.bcmd.insert(0, c),
            ).pack(side=tk.LEFT, padx=1, pady=2)

        # Upload file
        up_f = ttk.LabelFrame(f, text="Upload APK / File", padding=5)
        up_f.pack(fill=tk.X, pady=5)
        r1 = ttk.Frame(up_f)
        r1.pack(fill=tk.X)
        ttk.Label(r1, text="File:").pack(side=tk.LEFT)
        self.up_file = ttk.Entry(r1, width=60)
        self.up_file.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(
            r1, text="Browse",
            command=lambda: self.up_file.insert(
                0, filedialog.askopenfilename() or self.up_file.get()
            ),
        ).pack(side=tk.RIGHT)

        r2 = ttk.Frame(up_f)
        r2.pack(fill=tk.X)
        ttk.Label(r2, text="Dest:").pack(side=tk.LEFT)
        self.up_dest = ttk.Entry(r2, width=60)
        self.up_dest.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.up_dest.insert(0, "/sdcard/")
        ttk.Button(r2, text="📤 Upload All", command=self.bcast_upload).pack(
            side=tk.RIGHT
        )

        # Log output
        lf = ttk.LabelFrame(f, text="Output", padding=3)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        self.blog = tk.Text(lf, height=10, font=("Consolas", 8), bg="#111", fg="#0f0")
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.blog.yview)
        self.blog.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.blog.pack(fill=tk.BOTH, expand=True)

    def get_targets(self):
        t = self.btarget.get()
        if t == "All Devices":
            return [s for s in self.devices if self.devices[s].get("status") != "offline"]
        elif t == "Selected Only":
            return list(self.selected_devices)
        elif t.startswith("Group:"):
            g = t.replace("Group:", "").strip()
            return self.groups.get(g, [])
        return []

    def bcast_run(self):
        cmd = self.bcmd.get().strip()
        targets = self.get_targets()
        if not cmd or not targets:
            return
        delay = float(self.bdelay.get() or 0.3)
        self.log(f"📡 Broadcasting to {len(targets)} devices: {cmd}")

        def run():
            for s in targets:
                o = self.adb(f"-s {s} {cmd}", timeout=30)
                m = self.devices.get(s, {}).get("model", s)[:18]
                r = o[:80].replace("\n", " ")
                self.log(f"  {m}: {r}" if r else f"  {m}: ✅")
                if delay > 0:
                    time.sleep(delay)
            self.log("✅ Broadcast done")

        threading.Thread(target=run, daemon=True).start()

    def bcast_upload(self):
        fp = self.up_file.get().strip()
        dest = self.up_dest.get().strip() or "/sdcard/"
        if not fp or not os.path.exists(fp):
            self.log("❌ File not found")
            return
        targets = self.get_targets()
        if not targets:
            return
        fname = os.path.basename(fp)
        self.log(f"📤 Uploading {fname} to {len(targets)} devices...")

        def run():
            for s in targets:
                o = self.adb(f'-s {s} push "{fp}" {dest}', timeout=60)
                m = self.devices.get(s, {}).get("model", s)[:18]
                self.log(f"  {m}: {o[:60]}")
                time.sleep(0.2)
            self.log("✅ Upload done")

        threading.Thread(target=run, daemon=True).start()

    # ===================== GROUPS =====================
    def build_group_tab(self):
        f = ttk.Frame(self.group_tab, padding=10)
        f.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(f)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(left, text="Groups:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.glist = tk.Listbox(left, height=15, width=20)
        self.glist.pack(fill=tk.Y, expand=True, pady=5)
        self.glist.bind("<<ListboxSelect>>", lambda e: self.ref_grp())
        ttk.Button(left, text="+ New", command=self.new_grp).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="🗑 Delete", command=self.del_grp).pack(fill=tk.X, pady=2)

        right = ttk.Frame(f)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Members:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        cols = ttk.Frame(right)
        cols.pack(fill=tk.BOTH, expand=True)
        af = ttk.LabelFrame(cols, text="Available", padding=3)
        af.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.avail = tk.Listbox(af, font=("Consolas", 8))
        self.avail.pack(fill=tk.BOTH, expand=True)

        mf = ttk.Frame(cols)
        mf.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(mf, text=">>", command=self.add_grp).pack(pady=2)
        ttk.Button(mf, text="<<", command=self.rm_grp).pack(pady=2)

        gf = ttk.LabelFrame(cols, text="In Group", padding=3)
        gf.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=2)
        self.gdevs = tk.Listbox(gf, font=("Consolas", 8))
        self.gdevs.pack(fill=tk.BOTH, expand=True)

        self.refresh_groups()

    def new_grp(self):
        n = simpledialog.askstring("New Group", "Group name:")
        if n and n not in self.groups:
            self.groups[n] = []
            self.refresh_groups()

    def del_grp(self):
        s = self.glist.curselection()
        if s:
            n = self.glist.get(s[0])
            if n in self.groups:
                del self.groups[n]
                self.refresh_groups()

    def add_grp(self):
        s = self.glist.curselection()
        if not s:
            return
        g = self.glist.get(s[0])
        for i in self.avail.curselection():
            d = self.avail.get(i).split()[0]
            if d not in self.groups[g]:
                self.groups[g].append(d)
        self.ref_grp()

    def rm_grp(self):
        s = self.glist.curselection()
        if not s:
            return
        g = self.glist.get(s[0])
        for i in reversed(self.gdevs.curselection()):
            d = self.gdevs.get(i)
            if d in self.groups[g]:
                self.groups[g].remove(d)
        self.ref_grp()

    def refresh_groups(self):
        self.glist.delete(0, tk.END)
        for n in self.groups:
            self.glist.insert(tk.END, n)
        vals = ["All Devices", "Selected Only"]
        for n in self.groups:
            vals.append(f"Group: {n}")
        self.btarget["values"] = vals

    def ref_grp(self):
        self.avail.delete(0, tk.END)
        self.gdevs.delete(0, tk.END)
        s = self.glist.curselection()
        if not s:
            return
        g = self.glist.get(s[0])
        members = self.groups.get(g, [])
        for d, info in self.devices.items():
            if d in members:
                self.gdevs.insert(tk.END, d)
            else:
                self.avail.insert(tk.END, f"{d}  ({info.get('model', '?')[:18]})")

    # ===================== MONITOR =====================
    def build_monitor_tab(self):
        f = ttk.Frame(self.monitor_tab, padding=10)
        f.pack(fill=tk.BOTH, expand=True)

        sf = ttk.Frame(f)
        sf.pack(fill=tk.X)
        self.scards = {}
        for t, k, c in [
            ("Total", "total", "#0f3460"),
            ("Online", "online", "#4ecca3"),
            ("Offline", "offline", "#e23e57"),
            ("Mirror", "mirror", "#ffc107"),
            ("Known IPs", "known", "#7c3aed"),
        ]:
            cd = tk.Frame(sf, bg=c, bd=1, relief=tk.RAISED, width=140, height=70)
            cd.pack(side=tk.LEFT, padx=4, pady=5)
            cd.pack_propagate(False)
            tk.Label(cd, text=t, bg=c, fg="white", font=("Segoe UI", 8)).pack(pady=(5, 0))
            vl = tk.Label(cd, text="0", bg=c, fg="white", font=("Segoe UI", 20, "bold"))
            vl.pack(expand=True)
            self.scards[k] = vl

        lf = ttk.LabelFrame(f, text="Health Log", padding=3)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        tb = ttk.Frame(lf)
        tb.pack(fill=tk.X)
        ttk.Button(tb, text="Clear", command=lambda: self.hlog.delete(1.0, tk.END)).pack(
            side=tk.RIGHT
        )
        ttk.Button(tb, text="Export", command=self.exp_log).pack(side=tk.RIGHT, padx=2)
        ttk.Label(
            tb,
            text=f"Auto-scan: {'ON' if self.settings.get('auto_scan') else 'OFF'} | "
                 f"Subnet: {self.settings.get('subnet')}.* | "
                 f"OS: {platform.system()}",
            font=("Segoe UI", 7), foreground="#666",
        ).pack(side=tk.LEFT)

        self.hlog = tk.Text(lf, height=15, font=("Consolas", 8), bg="#111", fg="#0f0")
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.hlog.yview)
        self.hlog.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.hlog.pack(fill=tk.BOTH, expand=True)

        self.update_monitor_stats()

    def update_monitor_stats(self):
        self.scards["total"].config(text=str(len(self.devices)))
        online = sum(1 for d in self.devices.values() if d.get("status") != "offline")
        self.scards["online"].config(text=str(online))
        self.scards["offline"].config(text=str(len(self.devices) - online))
        self.scards["mirror"].config(text=str(len(self.processes)))
        self.scards["known"].config(text=str(len(self.settings.get("known_ips", []))))
        self.root.after(3000, self.update_monitor_stats)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.hlog.insert(tk.END, f"[{ts}] {msg}\n")
        self.hlog.see(tk.END)

    def exp_log(self):
        f = filedialog.asksaveasfilename(defaultextension=".txt")
        if f:
            with open(f, "w") as fp:
                fp.write(self.hlog.get(1.0, tk.END))

    # ===================== SETTINGS =====================
    def open_settings(self):
        w = tk.Toplevel(self.root, padx=15, pady=10)
        w.title("Settings")
        w.geometry("580x680")
        w.transient(self.root)
        w.grab_set()

        r = 0
        ttk.Label(w, text=f"Platform: {platform.system()}").grid(
            row=r, column=1, sticky=tk.E
        )
        r += 1

        ttk.Label(w, text="scrcpy Path:").grid(row=r, column=0, sticky=tk.W, pady=3)
        pv = tk.StringVar(value=self.settings.get("scrcpy_path", ""))
        ttk.Entry(w, textvariable=pv, width=50).grid(row=r, column=1, pady=3)
        r += 1

        ttk.Label(w, text="adb Path:").grid(row=r, column=0, sticky=tk.W, pady=3)
        av = tk.StringVar(value=self.settings.get("adb_path", ""))
        ttk.Entry(w, textvariable=av, width=50).grid(row=r, column=1, pady=3)
        r += 1

        ttk.Separator(w, orient=tk.HORIZONTAL).grid(
            row=r, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        r += 1

        ttk.Label(w, text="Mirror Settings:", font=("Segoe UI", 9, "bold")).grid(
            row=r, column=0, columnspan=3, sticky=tk.W
        )
        r += 1

        ttk.Label(w, text="Bitrate:").grid(row=r, column=0, sticky=tk.W)
        bv = ttk.Combobox(
            w, values=["512K", "1M", "2M", "4M", "8M", "16M"], width=10
        )
        bv.set(self.settings.get("default_bitrate", "2M"))
        bv.grid(row=r, column=1, sticky=tk.W)
        r += 1

        ttk.Label(w, text="Max Size:").grid(row=r, column=0, sticky=tk.W)
        sv = tk.IntVar(value=self.settings.get("default_max_size", 800))
        ttk.Spinbox(w, from_=240, to=1920, textvariable=sv, width=10).grid(
            row=r, column=1, sticky=tk.W
        )
        r += 1

        ttk.Label(w, text="Max FPS:").grid(row=r, column=0, sticky=tk.W)
        fv = tk.IntVar(value=self.settings.get("default_max_fps", 10))
        ttk.Spinbox(w, from_=1, to=60, textvariable=fv, width=10).grid(
            row=r, column=1, sticky=tk.W
        )
        r += 1

        sov = tk.BooleanVar(value=self.settings.get("default_screen_off", True))
        ttk.Checkbutton(w, text="Screen Off (-S)", variable=sov).grid(
            row=r, column=0, columnspan=2, sticky=tk.W
        )
        r += 1

        pov = tk.BooleanVar(value=self.settings.get("default_power_on_close", True))
        ttk.Checkbutton(w, text="Power On Close", variable=pov).grid(
            row=r, column=0, columnspan=2, sticky=tk.W
        )
        r += 1

        ttk.Separator(w, orient=tk.HORIZONTAL).grid(
            row=r, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        r += 1

        ttk.Label(w, text="Grid Layout:", font=("Segoe UI", 9, "bold")).grid(
            row=r, column=0, columnspan=3, sticky=tk.W
        )
        r += 1

        ttk.Label(w, text="Devices per page:").grid(row=r, column=0, sticky=tk.W)
        gpv = tk.IntVar(value=self.settings.get("grid_per_page", 20))
        ttk.Spinbox(w, from_=5, to=100, textvariable=gpv, width=10).grid(
            row=r, column=1, sticky=tk.W
        )
        r += 1

        ttk.Separator(w, orient=tk.HORIZONTAL).grid(
            row=r, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        r += 1

        ttk.Label(w, text="Network:", font=("Segoe UI", 9, "bold")).grid(
            row=r, column=0, columnspan=3, sticky=tk.W
        )
        r += 1

        asv = tk.BooleanVar(value=self.settings.get("auto_scan", True))
        ttk.Checkbutton(w, text="Auto-scan on startup", variable=asv).grid(
            row=r, column=0, columnspan=2, sticky=tk.W
        )
        r += 1

        arv = tk.BooleanVar(value=self.settings.get("auto_reconnect", True))
        ttk.Checkbutton(w, text="Auto-reconnect known devices", variable=arv).grid(
            row=r, column=0, columnspan=2, sticky=tk.W
        )
        r += 1

        ttk.Label(w, text="Subnet:").grid(row=r, column=0, sticky=tk.W)
        snv = tk.StringVar(value=self.settings.get("subnet", "192.168.1"))
        ttk.Entry(w, textvariable=snv, width=15).grid(row=r, column=1, sticky=tk.W)
        r += 1

        ttk.Label(w, text="IP Range:").grid(row=r, column=0, sticky=tk.W)
        frmv = tk.IntVar(value=self.settings.get("scan_range_start", 1))
        ttk.Spinbox(w, from_=1, to=254, textvariable=frmv, width=6).grid(
            row=r, column=1, sticky=tk.W, padx=(0, 5)
        )
        tov = tk.IntVar(value=self.settings.get("scan_range_end", 254))
        ttk.Spinbox(w, from_=1, to=254, textvariable=tov, width=6).grid(
            row=r, column=1, sticky=tk.W, padx=(50, 0)
        )
        ttk.Label(w, text="to").grid(row=r, column=1)
        r += 1

        ttk.Label(w, text="Health check (s):").grid(row=r, column=0, sticky=tk.W)
        civ = tk.IntVar(value=self.settings.get("check_interval", 5))
        ttk.Spinbox(w, from_=2, to=30, textvariable=civ, width=10).grid(
            row=r, column=1, sticky=tk.W
        )
        r += 1

        ttk.Separator(w, orient=tk.HORIZONTAL).grid(
            row=r, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        r += 1

        chv = tk.BooleanVar(value=self.settings.get("charge_mode", False))
        ttk.Checkbutton(
            w, text="🔋 Charge Mode (disable charging, 1-5 devices only)",
            variable=chv,
        ).grid(row=r, column=0, columnspan=3, sticky=tk.W)
        r += 1
        ttk.Label(
            w,
            text="* Auto-disabled when >5 devices. Saves USB port power.",
            font=("Segoe UI", 7), fg="#666",
        ).grid(row=r, column=0, columnspan=3, sticky=tk.W)
        r += 1

        def save():
            self.settings["scrcpy_path"] = pv.get()
            self.settings["adb_path"] = av.get()
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
            self.settings["check_interval"] = civ.get()
            self.settings["charge_mode"] = chv.get()
            self.save_settings()
            self.rebuild_grid()
            w.destroy()
            self.log("⚙ Settings saved")

        ttk.Button(w, text="💾 Save", command=save).grid(row=r, column=0, pady=10)

    # ===================== ABOUT =====================
    def show_about(self):
        messagebox.showinfo(
            "scrcpy Farm",
            f"scrcpy Farm v3.0\n\n"
            f"Cross-Platform Android Farm Manager\n"
            f"Platform: {platform.system()} {platform.machine()}\n\n"
            f"Supports 100+ devices via TCP/IP\n"
            f"Auto-scan, grid pagination, broadcast, groups\n\n"
            f"Built on scrcpy by Genymobile",
        )

    # ===================== CLOSE =====================
    def on_close(self):
        self.running = False
        for s in list(self.processes.keys()):
            self.stop_mirror(s)
        self.save_known_ips()
        self.save_settings()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DeviceFarm(root)
    root.mainloop()
