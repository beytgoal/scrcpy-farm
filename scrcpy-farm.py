#!/usr/bin/env python3
"""
Scrcpy Farm v5.2 — Embedded Multi-Session Display
Approach: scrcpy window reparented into PyQt6 grid via win32gui
Based on proven approach from degentod/scrcpy-gui
"""

import sys
import subprocess
import os
import time
import platform
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QFrame, QScrollArea, QFileDialog,
    QStatusBar, QDialog, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush

IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    import win32gui
    import win32con

# =====================================================================
# PATHS
# =====================================================================
if IS_WINDOWS:
    APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    DEFAULT_SCRCPY = "C:\\scrcpy\\scrcpy.exe"
    DEFAULT_ADB = "C:\\scrcpy\\adb.exe"
    if (APP_DIR / "scrcpy.exe").exists():
        DEFAULT_SCRCPY = str(APP_DIR / "scrcpy.exe")
    if (APP_DIR / "adb.exe").exists():
        DEFAULT_ADB = str(APP_DIR / "adb.exe")
elif platform.system() == "Darwin":
    DEFAULT_SCRCPY = "/opt/homebrew/bin/scrcpy"
    DEFAULT_ADB = "/opt/homebrew/bin/adb"
    if not Path(DEFAULT_SCRCPY).exists():
        DEFAULT_SCRCPY = "/usr/local/bin/scrcpy"
    if not Path(DEFAULT_ADB).exists():
        DEFAULT_ADB = "/usr/local/bin/adb"
else:
    DEFAULT_SCRCPY = "/usr/bin/scrcpy"
    DEFAULT_ADB = "/usr/bin/adb"

SETTINGS_FILE = Path.home() / ".scrcpy-farm.json"

def load_settings():
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"scrcpy_path": DEFAULT_SCRCPY, "adb_path": DEFAULT_ADB}

def save_settings(s):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass

def get_startupinfo():
    if IS_WINDOWS:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        return si
    return None

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           startupinfo=get_startupinfo())
        return r.stdout.strip()
    except Exception:
        return ""

def get_devices(adb):
    output = run_cmd([adb, "devices"])
    devices = []
    for line in output.split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices

# =====================================================================
# DARK THEME
# =====================================================================
DARK_STYLE = """
QMainWindow { background-color: #0d1117; }
QWidget { background-color: #0d1117; color: #e5e5ea; font-family: 'Segoe UI', sans-serif; }
QPushButton {
    background-color: #1f6feb; color: white; border: none;
    border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: 600;
}
QPushButton:hover { background-color: #388bfd; }
QPushButton:pressed { background-color: #1a5276; }
QStatusBar { background: #161b22; border-top: 1px solid #30363d; color: #8b949e; }
QScrollArea { border: none; background: transparent; }
QLabel { color: #e5e5ea; }
QScrollBar:vertical {
    background: #0d1117; width: 8px; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #30363d; border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #484f58; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

CARD_STYLE = """
QFrame#DeviceCard {
    background-color: #161b22;
    border: 2px solid #30363d;
    border-radius: 10px;
}
QFrame#DeviceCard:hover {
    border-color: #58a6ff;
}
"""

# =====================================================================
# DEVICE CARD
# =====================================================================
class DeviceCard(QFrame):
    def __init__(self, serial, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.setObjectName("DeviceCard")
        self.setStyleSheet(CARD_STYLE)
        self.setFixedSize(300, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #f39c12; font-size: 12px; background: transparent;")
        header.addWidget(self.status_dot)

        self.model_label = QLabel(serial[:18])
        self.model_label.setStyleSheet("color: #e5e5ea; font-size: 12px; font-weight: bold; background: transparent;")
        header.addStretch()
        layout.addLayout(header)

        # Container for scrcpy window
        self.video_container = QWidget()
        self.video_container.setObjectName("VideoFrame")
        self.video_container.setStyleSheet("background-color: #0d1117; border-radius: 6px;")
        self.video_container.setMinimumSize(280, 420)
        self.video_container.mousePressEvent = self._on_click
        layout.addWidget(self.video_container, 1)

        # Sideload button
        self.sideload_btn = QPushButton("Sideload APK")
        self.sideload_btn.setFixedHeight(28)
        self.sideload_btn.setStyleSheet("""
            QPushButton { background: #21262d; color: #8b949e; border-radius: 4px; font-size: 10px; }
            QPushButton:hover { background: #30363d; color: #e5e5ea; }
        """)
        self.sideload_btn.clicked.connect(self._sideload)
        layout.addWidget(self.sideload_btn)

        self.process = None
        self._embed_thread = None

    def start_mirror(self, scrcpy_path):
        """Launch scrcpy and embed its window into video_container."""
        if self.process:
            return

        cmd = [scrcpy_path, "-s", self.serial, "--window-title", f"scrcpy_{self.serial}"]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=get_startupinfo(),
            )
            self.status_dot.setStyleSheet("color: #f39c12; font-size: 12px; background: transparent;")
            self.model_label.setText(f"{self.serial[:15]} · connecting...")

            # Start embedding in background thread
            if IS_WINDOWS:
                self._embed_thread = EmbedThread(self.serial, self.video_container)
                self._embed_thread.embedded.connect(self._on_embedded)
                self._embed_thread.error.connect(self._on_embed_error)
                self._embed_thread.start()
            else:
                # Linux/macOS: just show status
                self.model_label.setText(f"{self.serial[:15]} · mirroring")
                self.status_dot.setStyleSheet("color: #2ecc71; font-size: 12px; background: transparent;")

        except Exception as e:
            self.model_label.setText(f"{self.serial[:10]} · error")

    def _on_embedded(self):
        self.status_dot.setStyleSheet("color: #2ecc71; font-size: 12px; background: transparent;")
        self.model_label.setText(f"{self.serial[:15]} · mirrored")

    def _on_embed_error(self, msg):
        self.model_label.setText(f"{self.serial[:10]} · {msg[:20]}")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 12px; background: transparent;")

    def stop_mirror(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None
        if self._embed_thread:
            self._embed_thread.stop()
            self._embed_thread = None

    def _on_click(self, event):
        """Forward click to embedded scrcpy window."""
        if IS_WINDOWS and self.process:
            hwnd = win32gui.FindWindow(None, f"scrcpy_{self.serial}")
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)

    def _sideload(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK files (*.apk)")
        if path:
            adb = load_settings().get("adb_path", DEFAULT_ADB)
            r = run_cmd([adb, "-s", self.serial, "install", "-r", path], timeout=60)
            if "Success" in r:
                self.model_label.setText(f"{self.serial[:15]} ✓")

    def closeEvent(self, event):
        self.stop_mirror()
        super().closeEvent(event)


# =====================================================================
# EMBED THREAD — finds scrcpy window and reparents into PyQt widget
# =====================================================================
class EmbedThread(QThread):
    embedded = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, serial, container_widget, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.container = container_widget
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        if not IS_WINDOWS:
            return

        window_title = f"scrcpy_{self.serial}"
        hwnd = None

        # Wait for scrcpy window to appear (up to 15 seconds)
        for _ in range(150):
            if self._stop:
                return
            hwnd = win32gui.FindWindow(None, window_title)
            if hwnd:
                break
            time.sleep(0.1)

        if not hwnd:
            self.error.emit("window not found")
            return

        # Get container's window handle
        container_hwnd = int(self.container.winId())

        # Reparent scrcpy window into our container
        try:
            win32gui.SetParent(hwnd, container_hwnd)

            # Resize to fit container
            self.container.updateGeometry()
            rect = self.container.geometry()
            win32gui.MoveWindow(hwnd, 0, 0, rect.width(), rect.height(), True)

            # Remove title bar / borders
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            style = style & ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_BORDER)
            style |= win32con.WS_CHILD
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

            self.embedded.emit()

        except Exception as e:
            self.error.emit(str(e)[:20])


# =====================================================================
# MAIN WINDOW
# =====================================================================
class ScrcpyFarmWindow(QMainWindow):
    def __init__(self, initial_devices=None):
        super().__init__()
        self.setWindowTitle("Scrcpy Farm v5.2")
        self.setMinimumSize(1200, 800)
        self.resize(1600, 900)

        self.settings = load_settings()
        self.cards = {}
        self.known_devices = set()

        self._build_ui()
        self.setStyleSheet(DARK_STYLE)

        # Poll devices
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_devices)
        self.poll_timer.start(3000)

        # Initial scan
        QTimer.singleShot(500, self._poll_devices)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        title = QLabel("Scrcpy Farm")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #e5e5ea; background: transparent;")
        header.addWidget(title)
        header.addStretch()

        self.stat_label = QLabel("Devices: 0")
        self.stat_label.setStyleSheet("color: #8b949e; font-size: 13px; background: transparent;")
        header.addWidget(self.stat_label)

        settings_btn = QPushButton("Settings")
        settings_btn.setFixedHeight(34)
        settings_btn.clicked.connect(self._open_settings)
        header.addWidget(settings_btn)

        main_layout.addLayout(header)

        # Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.grid_widget)
        main_layout.addWidget(scroll, 1)

        # Status
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Ready — waiting for devices")

    def _poll_devices(self):
        adb = self.settings.get("adb_path", DEFAULT_ADB)
        devices = get_devices(adb)

        # Remove disconnected
        for serial in list(self.cards.keys()):
            if serial not in devices:
                card = self.cards.pop(serial)
                self.grid_layout.removeWidget(card)
                card.stop_mirror()
                card.deleteLater()

        # Add new + auto mirror
        for serial in devices:
            if serial not in self.cards:
                card = DeviceCard(serial)
                self.cards[serial] = card

                # Get model
                model = run_cmd([adb, "-s", serial, "shell", "getprop", "ro.product.model"])
                if model:
                    card.model_label.setText(model[:18])

                # Add to grid
                count = self.grid_layout.count()
                cols = max(1, self.width() // 320)
                self.grid_layout.addWidget(card, count // cols, count % cols)

                # Auto start mirror
                scrcpy = self.settings.get("scrcpy_path", DEFAULT_SCRCPY)
                card.start_mirror(scrcpy)

        total = len(self.cards)
        self.stat_label.setText(f"Devices: {total}")
        self.statusBar().showMessage(f"Connected: {total}")

    def _open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setMinimumWidth(450)
        dlg.setStyleSheet("""
            QDialog { background: #161b22; color: #e5e5ea; }
            QLabel { color: #e5e5ea; background: transparent; }
            QLineEdit {
                background: #0d1117; color: #e5e5ea; border: 1px solid #30363d;
                border-radius: 6px; padding: 6px 10px; font-size: 13px;
            }
            QLineEdit:focus { border-color: #58a6ff; }
            QPushButton { background: #1f6feb; color: white; border: none;
                          border-radius: 6px; padding: 8px 20px; font-weight: 600; }
        """)

        form = QFormLayout(dlg)
        scrcpy_edit = QLineEdit(self.settings.get("scrcpy_path", DEFAULT_SCRCPY))
        adb_edit = QLineEdit(self.settings.get("adb_path", DEFAULT_ADB))
        form.addRow("Scrcpy:", scrcpy_edit)
        form.addRow("ADB:", adb_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(lambda: self._save(scrcpy_edit.text(), adb_edit.text(), dlg))
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        dlg.exec()

    def _save(self, scrcpy, adb, dlg):
        self.settings["scrcpy_path"] = scrcpy
        self.settings["adb_path"] = adb
        save_settings(self.settings)
        dlg.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reposition cards on resize
        cols = max(1, self.width() // 320)
        for i, serial in enumerate(self.cards.keys()):
            card = self.cards[serial]
            self.grid_layout.addWidget(card, i // cols, i % cols)
            # Resize embedded window
            if IS_WINDOWS and card.process:
                hwnd = win32gui.FindWindow(None, f"scrcpy_{serial}")
                if hwnd:
                    rect = card.video_container.geometry()
                    win32gui.MoveWindow(hwnd, 0, 0, rect.width(), rect.height(), True)

    def closeEvent(self, event):
        self.poll_timer.stop()
        for card in self.cards.values():
            card.stop_mirror()
        super().closeEvent(event)


# =====================================================================
# SPLASH SCREEN
# =====================================================================
class SplashLoading(QWidget):
    def __init__(self, on_finish):
        super().__init__()
        self.on_finish = on_finish
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(400, 200)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QHBoxLayout()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setSpacing(2)

        rain = QLabel("scrcpy")
        rain.setFont(QFont("Segoe UI", 36, QFont.Weight.Light))
        rain.setStyleSheet("color: #8b949e; background: transparent;")

        farm = QLabel("Farm")
        farm.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        farm.setStyleSheet("color: #58a6ff; background: transparent;")

        logo.addWidget(rain)
        logo.addWidget(farm)
        layout.addLayout(logo)

        self.loading = QLabel("LOADING...")
        self.loading.setFont(QFont("Segoe UI", 9))
        self.loading.setStyleSheet("color: #484f58; background: transparent; letter-spacing: 4px;")
        self.loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.loading)

        self._timer = QTimer(self)
        self._timer.singleShot(2000, self._finish)

    def _finish(self):
        self.close()
        self.on_finish()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#0d1117")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 15, 15)


# =====================================================================
# MAIN
# =====================================================================
def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    def launch():
        devices = get_devices(load_settings().get("adb_path", DEFAULT_ADB))
        win = ScrcpyFarmWindow(devices)
        win.show()

    splash = SplashLoading(launch)
    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
