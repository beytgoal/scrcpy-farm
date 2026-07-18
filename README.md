# scrcpy Farm 🖥️📱

> **Cross-Platform Multi-Device Android Farm Manager**
> Manage 50-100+ Android devices simultaneously — auto-scan, auto-pair, screen-off, broadcast, and monitor from one GUI.

[![Platform: Windows](https://img.shields.io/badge/Windows-0078D6?logo=windows)](https://github.com/beytgoal/scrcpy-farm)
[![Platform: Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux)](https://github.com/beytgoal/scrcpy-farm)
[![Platform: macOS](https://img.shields.io/badge/macOS-000000?logo=apple)](https://github.com/beytgoal/scrcpy-farm)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📸 Preview

```
┌────────────────────────────────────────────────────────────┐
│  scrcpy Farm — Android Device Manager          — □ ×       │
├────────────────────────────────────────────────────────────┤
│ 📱 Devices  │ 📡 Broadcast  │ 📁 Groups  │ 📊 Monitor     │
├────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│ │Samsung   │ │Xiaomi    │ │Google    │ │OnePlus   │      │
│ │● online  │ │● mirror  │ │● online  │ │● offline │      │
│ │🔋 85%    │ │🔋 92%    │ │🔋 67%    │ │🔋 ?%    │      │
│ │🤖 14     │ │🤖 13     │ │🤖 15     │ │🤖 ?     │      │
│ │▶ ☐      │ │⏹ ☐      │ │▶ ☐      │ │▶ ☐      │      │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│ ◀ Page 1/5 ▶                   20 shown | 87 total        │
├────────────────────────────────────────────────────────────┤
│ Devices: 87 | Online: 73 | Mirror: 45 | Page 1/5          │
└────────────────────────────────────────────────────────────┘
```

## ✨ Features

### 📱 Device Management
- **Auto-scan network** — scans your subnet on startup, auto-connects via ADB over TCP/IP
- **Auto-pair** — sequentially pairs discovered devices, no manual input needed
- **Auto-save IPs** — known devices are remembered and reconnected on next launch
- **Screen-off mirroring** (`-S`) — display on PC while phone screen stays off (saves battery)
- **Power-on-close** — phone screen turns back on when scrcpy window is closed
- **Low bandwidth mode** — per-device bitrate, resolution, and FPS control
- **USB and TCP/IP** — works with USB-connected devices AND wireless TCP/IP

### 📊 Grid View with Pagination
- Device cards with model, status, battery, Android version, IP
- Color-coded status: 🟢 online / 🔴 offline / 🟡 mirroring
- **Pagination** — configurable devices per page (default 20)
- Page navigation (◀ Prev / Next ▶)
- Multi-select checkboxes per device

### 📡 Broadcast
- **ADB command broadcast** — send one command to all/selected/group devices
- **Preset commands** — tap, swipe, home, back, power, volume, enter
- **File upload** — push APK or files to all devices simultaneously
- **Configurable delay** between devices to prevent network congestion

### 📁 Groups
- Create named device groups (e.g. "Floor 1", "VIP", "Testing")
- Drag devices between available/in-group lists
- Broadcast targets can be filtered by group

### 📊 Health Monitor
- Live device count: total, online, offline, mirror active
- Known IPs saved count
- Real-time health log (green-on-black terminal style)
- Exportable logs

### 🔋 Charge Mode
- Disables battery charging via ADB for connected devices
- **Only active when ≤5 devices** — auto-disables when more are connected
- Saves USB port power for large farms

---

## 🚀 Quick Start

### Prerequisites

| Tool | Windows | Linux | macOS |
|------|---------|-------|-------|
| **scrcpy** | [Download](https://github.com/Genymobile/scrcpy/releases/latest) | `sudo apt install scrcpy` | `brew install scrcpy` |
| **ADB** | Included with scrcpy | `sudo apt install adb` | `brew install android-platform-tools` |
| **Python 3.8+** | [Download](https://python.org) | `sudo apt install python3` | `brew install python-tk` |

### Run with Python

```bash
# Clone the repo
git clone https://github.com/beytgoal/scrcpy-farm.git
cd scrcpy-farm

# Run directly (no installation needed)
python3 scrcpy-farm.py
```

### Build Standalone Binary

**Windows — double-click:**
```
build\windows\build.bat
```
Result: `scrcpy-farm.exe` on your desktop.

**Linux:**
```bash
chmod +x build/linux/build.sh
./build/linux/build.sh
```
Result: `dist/scrcpy-farm`

**macOS:**
```bash
chmod +x build/macos/build.sh
./build/macos/build.sh
```
Result: `dist/scrcpy-farm.app`

---

## 🔧 How to Set Up 50-100 Devices

### Recommended Architecture

```
                    ┌─────────────────┐
                    │  PC / Server     │
                    │  scrcpy Farm     │
                    └────────┬────────┘
                             │ LAN (Gigabit)
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ AP/Router 1 │         │ AP/Router 2 │         │ AP/Router 3 │
   │ 192.168.1.x │         │ 192.168.2.x │         │ 192.168.3.x │
   └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
          │ 25-30 devices         │ 25-30 devices         │ 25-30 devices
    ┌─────┴─────┐           ┌─────┴─────┐           ┌─────┴─────┐
    │ Phones    │           │ Phones    │           │ Phones    │
    │ (WiFi)    │           │ (WiFi)    │           │ (WiFi)    │
    └───────────┘           └───────────┘           └───────────┘
```

### Step 1: Initial Pairing (one time per device)

Each device needs one USB pairing session:

```bash
# Connect phone via USB
adb devices                     # verify detected
adb -s <SERIAL> tcpip 5555      # enable TCP/IP mode
# Disconnect USB, phone stays on charger/WiFi
adb connect 192.168.1.101:5555  # connect via WiFi
scrcpy-farm will auto-save this IP ✅
```

### Step 2: Let scrcpy-farm auto-scan

Launch the app — it will:
1. Reconnect all previously saved IPs
2. Scan your subnet for new devices (192.168.1.1-254)
3. Save any newly discovered IPs
4. Start health monitoring

### Step 3: Start mirroring

Select devices → click "▶ Start Sel" or "▶ Start All"

### Recommended Settings for Large Farms

| Device Count | Bitrate | Max Size | FPS | Bandwidth Needed |
|-------------|---------|----------|-----|-----------------|
| 10 devices | 8M | 1280 | 30 | ~240 Mbps |
| 20 devices | 4M | 1024 | 30 | ~240 Mbps |
| 50 devices | 2M | 800 | 30 | ~300 Mbps |
| 100 devices | 1M | 720 | 15 | ~150 Mbps |
| 100 devices (eco) | 512K | 480 | 10 | ~50 Mbps |

Set these in **Settings → Mirror Settings**.

---

## 💻 USB Port Recommendations

### For Small Farms (1-10 devices via USB)

| USB Standard | Max Devices* | Notes |
|-------------|-------------|-------|
| **USB 2.0** | 3-5 | 480 Mbps shared — OK for low-res monitoring |
| **USB 3.0** | 5-8 | 5 Gbps shared — good for 720p |
| **USB 3.1/3.2** | 8-12 | 10-20 Gbps — best for USB farms |
| **USB-C (Thunderbolt 3/4)** | 10-15 | 40 Gbps — overkill but works |

\* *Per USB controller. Most PCs have 2-4 controllers.*

### For Large Farms (10-100+ devices via TCP/IP)

> **⚠️ USB is NOT recommended for large farms.**
> Use **WiFi / Ethernet + chargers** instead.

| Hardware | Recommendation |
|----------|---------------|
| **Phone chargers** | 1 per device or multi-port charging rack (e.g. 60-port USB charger) |
| **WiFi Router/AP** | WiFi 5 (AC) or WiFi 6 (AX) — one AP per ~30 devices |
| **Network Switch** | Gigabit Ethernet switch (48-port) for AP backbone |
| **PC Hardware** | Any modern PC — scrcpy-farm is lightweight |

### USB Power Saving

When using USB for smaller farms:
- Use **powered USB 3.0 hubs** (with external power adapter)
- Enable **Charge Mode** in scrcpy-farm settings (disables charging via ADB)
- Charge Mode auto-disables when >5 devices are connected
- For pure-data connections without power concerns, disable Charge Mode
- Use **quality cables** — cheap cables cause disconnections

---

## ⚙️ Configuration

Settings are stored in `~/.scrcpy-farm.json` (cross-platform).

| Setting | Default | Description |
|---------|---------|-------------|
| `subnet` | `192.168.1` | Subnet to scan for devices |
| `scan_range_start` | `1` | Start of IP scan range |
| `scan_range_end` | `254` | End of IP scan range |
| `grid_per_page` | `20` | Devices shown per grid page |
| `default_bitrate` | `2M` | Video bitrate per device |
| `default_max_size` | `800` | Max video size in pixels |
| `default_max_fps` | `30` | Max frames per second (1-240) |
| `auto_scan` | `true` | Auto-scan subnet on startup |
| `auto_reconnect` | `true` | Reconnect known devices |
| `charge_mode` | `false` | Disable ADB charging (≤5 devices) |
| `default_screen_off` | `true` | Turn off screen when mirroring |
| `default_power_on_close` | `true` | Power screen on when window closes |
| `check_interval` | `5` | Health check interval in seconds |

---

## 🛠️ Troubleshooting

### "adb not found"
- Windows: scrcpy includes adb.exe — set path in Settings
- Linux: `sudo apt install adb`
- macOS: `brew install android-platform-tools`

### "scrcpy not found"
- Windows: Download from [scrcpy releases](https://github.com/Genymobile/scrcpy/releases/latest)
- Linux: `sudo apt install scrcpy`
- macOS: `brew install scrcpy`

### Devices keep disconnecting
- Use **powered USB hub** for USB connections
- For TCP/IP: ensure stable WiFi signal (not 5 bars? move closer to AP)
- Reduce device count per WiFi access point (max ~30 per AP)
- Check `known_ips` in settings — auto-reconnect will handle temporary drops

### Battery drains quickly on USB
- Enable **Charge Mode** in settings (≤5 devices only)
- Use **powered USB hub** so the hub supplies power, not the PC
- For large farms: use dedicated **charging racks** + WiFi

### "Connection refused" on ADB connect
- Ensure USB debugging is enabled on the phone
- Run `adb tcpip 5555` while phone is connected via USB (one time)
- Reboot the phone if it still refuses

---

## 🧪 For Developers

### Project Structure
```
scrcpy-farm/
├── scrcpy-farm.py           # Main application
├── setup.py                 # Python package
├── README.md                # This file
├── LICENSE                  # MIT License
├── build/
│   ├── windows/
│   │   ├── build.bat        # Windows batch builder
│   │   └── installer.iss    # Inno Setup script
│   ├── linux/
│   │   └── build.sh         # Linux build script
│   └── macos/
│       └── build.sh         # macOS build script
└── dist/                    # Built binaries
```

### Requirements
- Python 3.8+ with tkinter (built-in on most platforms)
- scrcpy + adb on PATH

### Build from Source
```bash
pip install pyinstaller

# Windows
pyinstaller --onefile --noconsole scrcpy-farm.py

# Linux
pyinstaller --onefile scrcpy-farm.py

# macOS
pyinstaller --onefile --windowed scrcpy-farm.py
```

---

## 📋 Changelog

### v3.0 (Current)
- Cross-platform support (Windows, Linux, macOS)
- Auto-scan network + auto-pair devices
- Auto-save/load known IPs
- Grid pagination (configurable per page)
- Broadcast commands + file upload
- Device groups
- Health monitor dashboard
- Charge mode (auto ≤5 devices)
- Per-device bitrate/size/FPS control
- Dark theme grid UI

### v2.0
- Multi-device grid view
- TCP/IP connection manager
- Screen-off mirroring

### v1.0
- Single-device mirroring
- Basic USB detection

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

Built on [scrcpy](https://github.com/Genymobile/scrcpy) by Genymobile.

---

## 🙏 Acknowledgments

- [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) — the amazing screen mirroring tool
- Android ADB — for device communication
- Python tkinter — for the cross-platform GUI framework

---

*Made for Android device farms, testing labs, and developers who need to manage many devices at once.*
