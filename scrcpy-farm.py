#!/usr/bin/env python3
"""
Scrcpy Farm v5.0 — Embedded Multi-Session Display
PyQt6 + scrcpy H.264 pipe → frames → QLabel grid
No separate windows. All devices rendered inside one app.
"""

import sys
import os
import json
import subprocess
import platform
import threading
import signal
import struct
import time
from pathlib import Path
from collections import deque

# =====================================================================
# DEPENDENCY CHECK
# =====================================================================
_missing = []
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QPushButton, QFrame, QScrollArea, QFileDialog,
        QStatusBar, QSplitter, QGroupBox
    )
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QBuffer, QIODevice, QSize
    from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPalette, QIcon
except ImportError:
    _missing.append("PyQt6")

try:
    import av
except ImportError:
    _missing.append("av (PyAV)")

if _missing:
    print(f"ERROR: Missing packages: {', '.join(_missing)}")
    print("Run: pip install PyQt6 av")
    sys.exit(1)

# =====================================================================
# PLATFORM DETECTION
# =====================================================================
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"

if IS_WINDOWS:
    APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    DEFAULT_SCRCPY = "C:\\scrcpy\\scrcpy.exe"
    DEFAULT_ADB = "C:\\scrcpy\\adb.exe"
    # Also check same dir as exe/script
    if (APP_DIR / "scrcpy.exe").exists():
        DEFAULT_SCRCPY = str(APP_DIR / "scrcpy.exe")
    if (APP_DIR / "adb.exe").exists():
        DEFAULT_ADB = str(APP_DIR / "adb.exe")
elif IS_MACOS:
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

# =====================================================================
# SETTINGS
# =====================================================================
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

# =====================================================================
# HELPERS
# =====================================================================
def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
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
# SCRCPY VIDEO THREAD — pipes H.264 frames from scrcpy stdout
# =====================================================================
class ScrcpyVideoThread(QThread):
    """Runs scrcpy with --output-format=h264 --output=- to capture raw video.
    Decodes H.264 frames with PyAV and emits QPixmap signals."""
    frame_ready = pyqtSignal(object, str)  # QPixmap, serial
    error_occurred = pyqtSignal(str, str)   # error msg, serial
    stopped = pyqtSignal(str)               # serial

    def __init__(self, serial, scrcpy_path, adb_path, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.scrcpy_path = scrcpy_path
        self.adb_path = adb_path
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        scrcpy_dir = str(Path(self.scrcpy_path).parent)
        cmd = [
            self.scrcpy_path,
            f"--serial={self.serial}",
            "--no-window",  # scrcpy v3+ has this; v2.x does not
            "--output-format=h264",
            "--output=-",
        ]

        # If --no-window not supported, try without it
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=scrcpy_dir,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )
        except Exception as e:
            # Fallback: try without --no-window
            cmd_no_nw = [c for c in cmd if c != "--no-window"]
            try:
                proc = subprocess.Popen(
                    cmd_no_nw,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=scrcpy_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
                )
            except Exception as e2:
                self.error_occurred.emit(str(e2), self.serial)
                return

        # Decode H.264 stream with PyAV
        try:
            container = av.open(
                subprocess.Popen(
                    ["cat"],  # dummy — we feed data manually
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                ).stdout,
                format="h264",
            )
        except Exception:
            pass

        # Simpler approach: feed raw H.264 to av container
        self._decode_stream(proc)

        if proc.poll() is None:
            proc.terminate()
        self.stopped.emit(self.serial)

    def _decode_stream(self, proc):
        """Read H.264 from proc.stdout and decode frames with PyAV."""
        import io

        # Create a pipe-based container for H.264 input
        # We use a custom approach: read NAL units and decode
        stream = proc.stdout
        if not stream:
            self.error_occurred.emit("No stdout from scrcpy", self.serial)
            return

        # Build a custom IO adapter for PyAV
        buffer = bytearray()
        frame_count = 0

        while not self._stop:
            chunk = stream.read(65536)
            if not chunk:
                break
            buffer.extend(chunk)

            # Feed all available data to decoder
            # Try to decode complete frames from the buffer
            while len(buffer) > 0:
                try:
                    # Write buffer to a temporary pipe and decode
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.h264', delete=False) as tmp:
                        tmp.write(bytes(buffer))
                        tmp_path = tmp.name

                    container = av.open(tmp_path, format="h264")
                    for frame in container.decode(video=0):
                        if self._stop:
                            break
                        # Convert frame to QImage
                        img = frame.to_ndarray(format="rgb24")
                        h, w, ch = img.shape
                        bytes_per_line = ch * w
                        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                        pixmap = QPixmap.fromImage(qimg)
                        self.frame_ready.emit(pixmap, self.serial)
                        frame_count += 1

                    container.close()
                    os.unlink(tmp_path)
                    buffer.clear()
                    break  # Got frames, wait for more data

                except Exception:
                    # Incomplete frame, wait for more data
                    if len(buffer) > 10 * 1024 * 1024:  # 10MB safety
                        buffer.clear()
                    break

        if frame_count == 0:
            self.error_occurred.emit("No video frames decoded", self.serial)

# =====================================================================
# DEVICE CARD WIDGET
# =====================================================================
class DeviceCard(QFrame):
    """A card that displays one device's video feed inside the grid."""
    def __init__(self, serial, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            DeviceCard {
                background-color: #1a1a2e;
                border: 2px solid #16213e;
                border-radius: 8px;
            }
            DeviceCard:hover {
                border-color: #0f3460;
            }
        """)
        self.setFixedSize(260, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header: model + status
        header = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #2ecc71; font-size: 10px;")
        header.addWidget(self.status_dot)

        self.model_label = QLabel(serial[:15])
        self.model_label.setStyleSheet("color: white; font-size: 11px; font-weight: bold;")
        self.model_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.model_label)
        layout.addLayout(header)

        # Video feed
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(240, 400)
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px;")
        self.video_label.setText("Connecting...")
        self.video_label.setFont(QFont("Segoe UI", 10))
        self.video_label.setStyleSheet("""
            background-color: #0a0a15;
            border-radius: 4px;
            color: #666;
        """)
        layout.addWidget(self.video_label, 1)

        # Sideload button
        self.sideload_btn = QPushButton("Sideload APK")
        self.sideload_btn.setFixedHeight(28)
        self.sideload_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #1a5276; }
        """)
        self.sideload_btn.clicked.connect(self._sideload)
        layout.addWidget(self.sideload_btn)

        self.video_thread = None

    def update_frame(self, pixmap):
        """Update the video display with a new frame."""
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.video_label.setPixmap(scaled)

    def set_model(self, name):
        self.model_label.setText(name[:15])

    def set_online(self, online):
        if online:
            self.status_dot.setStyleSheet("color: #2ecc71; font-size: 10px;")
        else:
            self.status_dot.setStyleSheet("color: #e74c3c; font-size: 10px;")
            self.video_label.setText("Offline")
            self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #e74c3c;")

    def start_stream(self, scrcpy_path, adb_path):
        """Start the scrcpy video stream for this device."""
        if self.video_thread and self.video_thread.isRunning():
            return
        self.video_thread = ScrcpyVideoThread(self.serial, scrcpy_path, adb_path)
        self.video_thread.frame_ready.connect(self.update_frame)
        self.video_thread.error_occurred.connect(self._on_error)
        self.video_thread.stopped.connect(self._on_stopped)
        self.video_thread.start()
        self.video_label.setText("Starting mirror...")
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #f39c12;")

    def stop_stream(self):
        """Stop the scrcpy video stream."""
        if self.video_thread and self.video_thread.isRunning():
            self.video_thread.stop()
            self.video_thread.wait(3000)
            self.video_thread = None
        self.video_label.setText("Stopped")
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #666;")

    def _on_error(self, msg, serial):
        self.video_label.setText(f"Error: {msg[:50]}")
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #e74c3c;")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 10px;")

    def _on_stopped(self, serial):
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 10px;")

    def _sideload(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK files (*.apk)")
        if path:
            adb = load_settings().get("adb_path", DEFAULT_ADB)
            r = run_cmd([adb, "-s", self.serial, "install", "-r", path], timeout=60)
            if "Success" in r:
                self.model_label.setText(f"{self.serial[:15]} ✓")
            else:
                self.model_label.setText(f"{self.serial[:15]} ✗")

    def closeEvent(self, event):
        self.stop_stream()
        super().closeEvent(event)

# =====================================================================
# MAIN WINDOW
# =====================================================================
class ScrcpyFarmWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scrcpy Farm v5.0 — Embedded Display")
        self.setMinimumSize(1200, 800)
        self.resize(1600, 900)

        self.settings = load_settings()
        self.cards = {}         # serial -> DeviceCard
        self.known_devices = set()

        self._build_ui()
        self._apply_dark_theme()

        # Poll timer for device detection
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_devices)
        self.poll_timer.start(3000)
        self._poll_devices()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("Scrcpy Farm")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        header.addWidget(title)

        header.addStretch()

        self.stat_label = QLabel("Devices: 0 | Mirroring: 0")
        self.stat_label.setStyleSheet("color: #aaa; font-size: 12px;")
        header.addWidget(self.stat_label)

        settings_btn = QPushButton("Settings")
        settings_btn.setFixedHeight(32)
        settings_btn.clicked.connect(self._open_settings)
        header.addWidget(settings_btn)
        main_layout.addLayout(header)

        # Scrollable grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0d1117; }")

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.grid_widget)
        main_layout.addWidget(scroll, 1)

        # Status bar
        status = QStatusBar()
        status.setStyleSheet("color: #888; font-size: 11px;")
        self.setStatusBar(status)
        status.showMessage("Ready — waiting for devices")

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0d1117; }
            QWidget { background-color: #0d1117; color: white; }
            QPushButton {
                background-color: #1f6feb;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #388bfd; }
            QStatusBar { background: #161b22; border-top: 1px solid #30363d; }
            QScrollArea { background: #0d1117; }
            QLabel { color: white; }
        """)

    def _poll_devices(self):
        """Check for connected devices and auto-mirror."""
        adb = self.settings.get("adb_path", DEFAULT_ADB)
        devices = get_devices(adb)

        # Remove cards for disconnected devices
        for serial in list(self.cards.keys()):
            if serial not in devices:
                card = self.cards.pop(serial)
                self.grid_layout.removeWidget(card)
                card.stop_stream()
                card.deleteLater()
                self.known_devices.discard(serial)

        # Add cards for new devices
        for serial in devices:
            if serial not in self.cards:
                card = DeviceCard(serial)
                self.cards[serial] = card
                self.known_devices.add(serial)

                # Try to get device model
                model = run_cmd([adb, "-s", serial, "shell", "getprop", "ro.product.model"])
                if model:
                    card.set_model(model)

                self._add_card_to_grid(card)

                # Auto-start mirror
                card.start_stream(
                    self.settings.get("scrcpy_path", DEFAULT_SCRCPY),
                    adb,
                )

        self._update_stats()

    def _add_card_to_grid(self, card):
        """Add a device card to the grid (5 columns)."""
        count = self.grid_layout.count()
        cols = 5
        row = count // cols
        col = count % cols
        self.grid_layout.addWidget(card, row, col)

    def _update_stats(self):
        total = len(self.cards)
        mirroring = sum(1 for c in self.cards.values()
                        if c.video_thread and c.video_thread.isRunning())
        self.stat_label.setText(f"Devices: {total} | Mirroring: {mirroring}")
        self.statusBar().showMessage(
            f"Connected: {total} device(s) | Mirroring: {mirroring}"
        )

    def _open_settings(self):
        """Simple settings dialog."""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet("""
            QDialog { background: #161b22; color: white; }
            QLabel { color: white; }
            QLineEdit { background: #0d1117; color: white; border: 1px solid #30363d; border-radius: 4px; padding: 4px; }
            QPushButton { background: #1f6feb; color: white; border: none; border-radius: 4px; padding: 6px 16px; }
        """)

        form = QFormLayout(dlg)
        scrcpy_edit = QLineEdit(self.settings.get("scrcpy_path", DEFAULT_SCRCPY))
        adb_edit = QLineEdit(self.settings.get("adb_path", DEFAULT_ADB))
        form.addRow("Scrcpy path:", scrcpy_edit)
        form.addRow("ADB path:", adb_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(lambda: self._save_settings(scrcpy_edit.text(), adb_edit.text(), dlg))
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        dlg.exec()

    def _save_settings(self, scrcpy, adb, dlg):
        self.settings["scrcpy_path"] = scrcpy
        self.settings["adb_path"] = adb
        save_settings(self.settings)
        dlg.accept()

    def closeEvent(self, event):
        self.poll_timer.stop()
        for card in self.cards.values():
            card.stop_stream()
        super().closeEvent(event)

# =====================================================================
# ENTRY POINT
# =====================================================================
def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    window = ScrcpyFarmWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
