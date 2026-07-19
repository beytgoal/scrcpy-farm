#!/usr/bin/env python3
"""
Scrcpy Farm v5.1 — Embedded Multi-Session Display
Pipe scrcpy stdout H.264 → decode → render inside PyQt6 grid
"""

import sys
import os
import json
import subprocess
import platform
import threading
import signal
import time
import tempfile
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QPushButton, QFrame, QScrollArea, QFileDialog,
        QStatusBar, QDialog, QFormLayout, QLineEdit, QDialogButtonBox
    )
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
    from PyQt6.QtGui import QImage, QPixmap, QFont
except ImportError:
    print("ERROR: pip install PyQt6")
    sys.exit(1)

try:
    import cv2
    import numpy as np
except ImportError:
    print("ERROR: pip install opencv-python")
    sys.exit(1)

# =====================================================================
# PLATFORM
# =====================================================================
IS_WINDOWS = platform.system() == "Windows"

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
# VIDEO THREAD — pipe scrcpy stdout → OpenCV decode
# =====================================================================
class ScrcpyVideoThread(QThread):
    frame_ready = pyqtSignal(object, str)
    error_occurred = pyqtSignal(str, str)
    stopped = pyqtSignal(str)

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

        # Use scrcpy --output-format=h264 --output=- to pipe raw H.264 to stdout
        cmd = [
            self.scrcpy_path,
            f"--serial={self.serial}",
            "--no-display",
            "--output-format=h264",
            "--output=-",
        ]

        proc = None

        # Try with --no-display first, fallback without
        for args in [
            cmd,
            [a for a in cmd if a != "--no-display"],
            [self.scrcpy_path, f"--serial={self.serial}", "--output-format=h264", "--output=-"],
        ]:
            try:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=scrcpy_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
                )
                # Wait a bit to check if it started
                time.sleep(0.5)
                if proc.poll() is None:
                    break
                # Process already exited = bad args
                proc = None
            except Exception:
                proc = None

        if proc is None:
            self.error_occurred.emit("Cannot start scrcpy", self.serial)
            return

        # Read raw H.264 from stdout and decode with OpenCV
        self._decode_stream(proc)

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()

        self.stopped.emit(self.serial)

    def _decode_stream(self, proc):
        """Read H.264 stream from subprocess stdout, decode with OpenCV."""
        # OpenCV can read H.264 from a pipe if we wrap it
        # Write to a temp file and read with cv2.VideoCapture
        
        tmp_path = os.path.join(tempfile.gettempdir(), f"scrcpy_{self.serial}.h264")
        
        # Collect data in background, decode from file
        data_collector = threading.Thread(
            target=self._collect_data, args=(proc, tmp_path), daemon=True
        )
        data_collector.start()
        
        # Wait a moment for data to start flowing
        time.sleep(1.0)
        
        # Try to open with OpenCV
        frame_count = 0
        retries = 0
        max_retries = 20  # Wait up to 10 seconds for stream to start
        
        while not self._stop and retries < max_retries:
            try:
                cap = cv2.VideoCapture(tmp_path)
                if not cap.isOpened():
                    retries += 1
                    time.sleep(0.5)
                    continue
                
                while not self._stop:
                    ret, frame = cap.read()
                    if not ret:
                        # Check if collector is still running
                        if not data_collector.is_alive():
                            break
                        time.sleep(0.05)
                        continue
                    
                    # Convert BGR to RGB
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg)
                    self.frame_ready.emit(pixmap, self.serial)
                    frame_count += 1
                
                cap.release()
                break
                
            except Exception as e:
                retries += 1
                time.sleep(0.5)
        
        # Cleanup
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        
        if frame_count == 0:
            self.error_occurred.emit("No video frames", self.serial)

    def _collect_data(self, proc, tmp_path):
        """Collect H.264 data from subprocess stdout to file."""
        try:
            with open(tmp_path, "wb") as f:
                while not self._stop:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    f.flush()
        except Exception:
            pass

# =====================================================================
# DEVICE CARD
# =====================================================================
class DeviceCard(QFrame):
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
        """)
        self.setFixedSize(260, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #2ecc71; font-size: 10px;")
        header.addWidget(self.status_dot)

        self.model_label = QLabel(serial[:15])
        self.model_label.setStyleSheet("color: white; font-size: 11px; font-weight: bold;")
        self.model_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.model_label)
        layout.addLayout(header)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(240, 400)
        self.video_label.setText("Connecting...")
        self.video_label.setFont(QFont("Segoe UI", 10))
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #666;")
        layout.addWidget(self.video_label, 1)

        self.sideload_btn = QPushButton("Sideload APK")
        self.sideload_btn.setFixedHeight(28)
        self.sideload_btn.setStyleSheet("""
            QPushButton { background-color: #0f3460; color: white; border: none; border-radius: 4px; font-size: 10px; }
            QPushButton:hover { background-color: #1a5276; }
        """)
        self.sideload_btn.clicked.connect(self._sideload)
        layout.addWidget(self.sideload_btn)

        self.video_thread = None

    def update_frame(self, pixmap):
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.video_label.setPixmap(scaled)

    def set_model(self, name):
        self.model_label.setText(name[:15])

    def start_stream(self, scrcpy_path, adb_path):
        if self.video_thread and self.video_thread.isRunning():
            return
        self.video_thread = ScrcpyVideoThread(self.serial, scrcpy_path, adb_path)
        self.video_thread.frame_ready.connect(self.update_frame)
        self.video_thread.error_occurred.connect(self._on_error)
        self.video_thread.start()
        self.video_label.setText("Starting mirror...")
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #f39c12;")

    def stop_stream(self):
        if self.video_thread and self.video_thread.isRunning():
            self.video_thread.stop()
            self.video_thread.wait(5000)
            self.video_thread = None

    def _on_error(self, msg, serial):
        self.video_label.setText(f"Error:\n{msg[:50]}")
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #e74c3c; font-size: 9px;")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 10px;")

    def _sideload(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK files (*.apk)")
        if path:
            adb = load_settings().get("adb_path", DEFAULT_ADB)
            run_cmd([adb, "-s", self.serial, "install", "-r", path], timeout=60)

    def closeEvent(self, event):
        self.stop_stream()
        super().closeEvent(event)

# =====================================================================
# MAIN WINDOW
# =====================================================================
class ScrcpyFarmWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scrcpy Farm v5.1")
        self.setMinimumSize(1200, 800)
        self.resize(1600, 900)

        self.settings = load_settings()
        self.cards = {}

        self._build_ui()
        self._apply_dark_theme()

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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0d1117; }")

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.grid_widget)
        main_layout.addWidget(scroll, 1)

        status = QStatusBar()
        status.setStyleSheet("color: #888; font-size: 11px;")
        self.setStatusBar(status)
        status.showMessage("Ready")

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0d1117; }
            QWidget { background-color: #0d1117; color: white; }
            QPushButton {
                background-color: #1f6feb; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px;
            }
            QPushButton:hover { background-color: #388bfd; }
            QStatusBar { background: #161b22; border-top: 1px solid #30363d; }
            QLabel { color: white; }
        """)

    def _poll_devices(self):
        adb = self.settings.get("adb_path", DEFAULT_ADB)
        devices = get_devices(adb)

        for serial in list(self.cards.keys()):
            if serial not in devices:
                card = self.cards.pop(serial)
                self.grid_layout.removeWidget(card)
                card.stop_stream()
                card.deleteLater()

        for serial in devices:
            if serial not in self.cards:
                card = DeviceCard(serial)
                self.cards[serial] = card

                model = run_cmd([adb, "-s", serial, "shell", "getprop", "ro.product.model"])
                if model:
                    card.set_model(model)

                count = self.grid_layout.count()
                self.grid_layout.addWidget(card, count // 5, count % 5)

                card.start_stream(
                    self.settings.get("scrcpy_path", DEFAULT_SCRCPY),
                    adb,
                )

        total = len(self.cards)
        mirroring = sum(1 for c in self.cards.values() if c.video_thread and c.video_thread.isRunning())
        self.stat_label.setText(f"Devices: {total} | Mirroring: {mirroring}")

    def _open_settings(self):
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

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = ScrcpyFarmWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
