#!/usr/bin/env python3
"""
Scrcpy Farm v5.0 — Embedded Multi-Session Display
Uses scrcpy-server directly via ADB + TCP socket → PyAV decode → PyQt6 grid
No scrcpy.exe window. All video rendered inside the app.
"""

import sys
import os
import json
import subprocess
import platform
import threading
import socket
import struct
import time
import io
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
        QStatusBar, QDialog, QFormLayout, QLineEdit, QDialogButtonBox
    )
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
    from PyQt6.QtGui import QImage, QPixmap, QFont
except ImportError:
    _missing.append("PyQt6")

try:
    import av
except ImportError:
    _missing.append("av (PyAV)")

if _missing:
    print(f"ERROR: Missing: {', '.join(_missing)}")
    print("Run: pip install PyQt6 av")
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
SCRCPY_SERVER_JAR = "scrcpy-server-v4.1"  # filename inside release zip

# Base port for scrcpy-server TCP tunnels (each device gets its own port)
BASE_PORT = 27183

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

# Find scrcpy-server jar in scrcpy install dir
def find_scrcpy_server(scrcpy_path):
    scrcpy_dir = Path(scrcpy_path).parent
    # Look for scrcpy-server file (name varies by version)
    for pattern in ["scrcpy-server*", "scrcpy-server"]:
        matches = list(scrcpy_dir.glob(pattern))
        for m in matches:
            if m.is_file() and not m.suffix in ('.md', '.txt', '.log', '.bat', '.sh', '.py'):
                return str(m)
    return None

# =====================================================================
# SCRCPY VIDEO THREAD — connects to scrcpy-server via ADB TCP tunnel
# =====================================================================
class ScrcpyVideoThread(QThread):
    """Push scrcpy-server to device, open ADB forward, connect TCP socket,
    decode H.264 stream with PyAV, emit QPixmap frames."""
    frame_ready = pyqtSignal(object, str)   # QPixmap, serial
    error_occurred = pyqtSignal(str, str)   # error, serial
    stopped = pyqtSignal(str)

    def __init__(self, serial, adb_path, port, server_jar=None, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.adb_path = adb_path
        self.port = port
        self.server_jar = server_jar
        self._stop = False
        self._server_proc = None

    def stop(self):
        self._stop = True

    def run(self):
        adb = self.adb_path
        serial = self.serial
        port = self.port

        try:
            # Step 1: Find scrcpy-server jar
            if not self.server_jar:
                self.error_occurred.emit("scrcpy-server not found in scrcpy directory", serial)
                return

            # Step 2: Push scrcpy-server to device
            remote_path = "/data/local/tmp/scrcpy-server.jar"
            r = run_cmd([adb, "-s", serial, "push", self.server_jar, remote_path], timeout=15)
            if "pushed" not in r.lower() and "error" in r.lower():
                self.error_occurred.emit(f"Failed to push server: {r}", serial)
                return

            # Step 3: Set up ADB forward
            forward_key = f"tcp:{port}"
            run_cmd([adb, "-s", serial, "forward", forward_key, f"localabstract:scrcpy_{serial}"], timeout=5)

            # Step 4: Start scrcpy-server on device
            server_cmd = (
                f"CLASSPATH={remote_path} "
                f"app_process / com.genymobile.scrcpy.Server 4.1 "
                f"tunnel_forward=true "
                f"audio=false "
                f"control=false "
                f"cleanup=false "
                f"raw_stream=true "
                f"max_size=1024"
            )

            self._server_proc = subprocess.Popen(
                [adb, "-s", serial, "shell", server_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )

            # Step 5: Wait for server to start
            time.sleep(1.5)

            if self._server_proc.poll() is not None:
                stderr = self._server_proc.stderr.read().decode(errors="ignore")
                self.error_occurred.emit(f"Server exited: {stderr[:100]}", serial)
                return

            # Step 6: Connect TCP socket to get raw H.264
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("127.0.0.1", port))

            # Step 7: Read device name header (1 byte size + name)
            # When raw_stream=true, server sends device name first
            try:
                name_size = sock.recv(1)
                if name_size:
                    device_name = sock.recv(name_size[0])
            except Exception:
                pass  # raw_stream=true might skip header

            sock.settimeout(0.5)

            # Step 8: Decode H.264 stream
            self._decode_h264_stream(sock)

            sock.close()

        except Exception as e:
            self.error_occurred.emit(str(e)[:100], serial)

        finally:
            # Cleanup: remove ADB forward and kill server
            run_cmd([adb, "-s", serial, "forward", f"--remove", f"tcp:{port}"], timeout=3)
            if self._server_proc and self._server_proc.poll() is None:
                self._server_proc.terminate()
                try:
                    self._server_proc.wait(timeout=3)
                except Exception:
                    self._server_proc.kill()

            self.stopped.emit(self.serial)

    def _decode_h264_stream(self, sock):
        """Read raw H.264 from socket, decode frames with PyAV."""
        # Create av container for H.264 demuxing
        # We use a pipe-like approach: accumulate data, write to temp, decode

        buffer = bytearray()
        frame_count = 0

        while not self._stop:
            try:
                data = sock.recv(65536)
                if not data:
                    break
                buffer.extend(data)
            except socket.timeout:
                continue
            except Exception:
                break

            # Try to decode what we have
            if len(buffer) > 1024:  # At least 1KB before trying
                frames = self._try_decode_buffer(bytes(buffer))
                if frames:
                    for frame_data in frames:
                        qimg = QImage(
                            frame_data, frame_data.shape[1], frame_data.shape[0],
                            3 * frame_data.shape[1], QImage.Format.Format_RGB888
                        )
                        pixmap = QPixmap.fromImage(qimg)
                        self.frame_ready.emit(pixmap, self.serial)
                        frame_count += 1
                    buffer.clear()
                elif len(buffer) > 5 * 1024 * 1024:  # 5MB safety
                    buffer.clear()

        if frame_count == 0:
            self.error_occurred.emit("No video frames decoded", self.serial)

    def _try_decode_buffer(self, data):
        """Try to decode H.264 data with PyAV, return list of numpy arrays."""
        try:
            # Write to a temporary pipe-like structure
            container = av.open(io.BytesIO(data), format="h264")
            frames = []
            for frame in container.decode(video=0):
                frames.append(frame.to_ndarray(format="rgb24"))
            container.close()
            return frames
        except Exception:
            return []

# =====================================================================
# DEVICE CARD WIDGET
# =====================================================================
class DeviceCard(QFrame):
    """Displays one device's live video feed inside the grid."""
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

        # Header
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
        self.video_label.setText("Connecting...")
        self.video_label.setFont(QFont("Segoe UI", 10))
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #666;")
        layout.addWidget(self.video_label, 1)

        # Sideload button
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

    def set_online(self, online):
        if online:
            self.status_dot.setStyleSheet("color: #2ecc71; font-size: 10px;")
        else:
            self.status_dot.setStyleSheet("color: #e74c3c; font-size: 10px;")
            self.video_label.setText("Offline")
            self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #e74c3c;")

    def start_stream(self, adb_path, port, server_jar=None):
        if self.video_thread and self.video_thread.isRunning():
            return
        self.video_thread = ScrcpyVideoThread(self.serial, adb_path, port, server_jar)
        self.video_thread.frame_ready.connect(self.update_frame)
        self.video_thread.error_occurred.connect(self._on_error)
        self.video_thread.stopped.connect(self._on_stopped)
        self.video_thread.start()
        self.video_label.setText("Starting mirror...")
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #f39c12;")

    def stop_stream(self):
        if self.video_thread and self.video_thread.isRunning():
            self.video_thread.stop()
            self.video_thread.wait(5000)
            self.video_thread = None
        self.video_label.setText("Stopped")
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #666;")

    def _on_error(self, msg, serial):
        self.video_label.setText(f"Error:\n{msg[:40]}")
        self.video_label.setStyleSheet("background-color: #0a0a15; border-radius: 4px; color: #e74c3c; font-size: 9px;")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 10px;")

    def _on_stopped(self, serial):
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 10px;")

    def _sideload(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK files (*.apk)")
        if path:
            adb = load_settings().get("adb_path", DEFAULT_ADB)
            r = run_cmd([adb, "-s", self.serial, "install", "-r", path], timeout=60)
            if "Success" in r:
                self.model_label.setText(f"{self.serial[:12]} ✓")
            else:
                self.model_label.setText(f"{self.serial[:12]} ✗")

    def closeEvent(self, event):
        self.stop_stream()
        super().closeEvent(event)

# =====================================================================
# MAIN WINDOW
# =====================================================================
class ScrcpyFarmWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scrcpy Farm v5.0")
        self.setMinimumSize(1200, 800)
        self.resize(1600, 900)

        self.settings = load_settings()
        self.cards = {}
        self.device_ports = {}   # serial -> port number
        self.next_port = BASE_PORT
        self.server_jar = find_scrcpy_server(self.settings.get("scrcpy_path", DEFAULT_SCRCPY))

        self._build_ui()
        self._apply_dark_theme()

        # Poll for devices
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

        if self.server_jar:
            status.showMessage(f"Ready — server: {Path(self.server_jar).name}")
        else:
            status.showMessage("WARNING: scrcpy-server not found in scrcpy directory!")

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
            QScrollArea { background: #0d1117; }
            QLabel { color: white; }
        """)

    def _poll_devices(self):
        adb = self.settings.get("adb_path", DEFAULT_ADB)
        devices = get_devices(adb)

        # Remove disconnected
        for serial in list(self.cards.keys()):
            if serial not in devices:
                card = self.cards.pop(serial)
                port = self.device_ports.pop(serial, None)
                self.grid_layout.removeWidget(card)
                card.stop_stream()
                card.deleteLater()

        # Add new devices
        for serial in devices:
            if serial not in self.cards:
                # Assign unique port
                port = self.next_port
                self.next_port += 1
                self.device_ports[serial] = port

                card = DeviceCard(serial)
                self.cards[serial] = card

                # Get model
                model = run_cmd([adb, "-s", serial, "shell", "getprop", "ro.product.model"])
                if model:
                    card.set_model(model)

                self._add_card(card)

                # Auto-start mirror
                card.start_stream(adb, port, self.server_jar)

        self._update_stats()

    def _add_card(self, card):
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
        self.statusBar().showMessage(f"Connected: {total} | Mirroring: {mirroring}")

    def _open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet("""
            QDialog { background: #161b22; color: white; }
            QLabel { color: white; }
            QLineEdit { background: #0d1117; color: white; border: 1px solid #30363d;
                         border-radius: 4px; padding: 4px; }
            QPushButton { background: #1f6feb; color: white; border: none;
                          border-radius: 4px; padding: 6px 16px; }
        """)

        form = QFormLayout(dlg)
        scrcpy_edit = QLineEdit(self.settings.get("scrcpy_path", DEFAULT_SCRCPY))
        adb_edit = QLineEdit(self.settings.get("adb_path", DEFAULT_ADB))
        form.addRow("Scrcpy path:", scrcpy_edit)
        form.addRow("ADB path:", adb_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(lambda: self._save_and_close(scrcpy_edit.text(), adb_edit.text(), dlg))
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        dlg.exec()

    def _save_and_close(self, scrcpy, adb, dlg):
        self.settings["scrcpy_path"] = scrcpy
        self.settings["adb_path"] = adb
        save_settings(self.settings)
        self.server_jar = find_scrcpy_server(scrcpy)
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
