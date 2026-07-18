# scrcpy Farm v4.0 📱🖥️

> **Cross-Platform Multi-Device Android Farm Manager**
> Modern dark UI · Auto-download dependencies · 100+ devices · 30-240 FPS

[![Platform: Windows](https://img.shields.io/badge/Windows-0078D6?logo=windows)](https://github.com/beytgoal/scrcpy-farm)
[![Platform: Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux)](https://github.com/beytgoal/scrcpy-farm)
[![Platform: macOS](https://img.shields.io/badge/macOS-000000?logo=apple)](https://github.com/beytgoal/scrcpy-farm)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📸 Preview

Modern dark theme with device cards, stats bar, and grid pagination:

```
┌──────────────────────────────────────────────────────────────┐
│  📱 scrcpy Farm v4.0  🖥️ Windows            [🔄] [▶] [⚙] │
├──────────────────────────────────────────────────────────────┤
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│ │ 87     │ │  73    │ │  14    │ │  45    │ │  31    │    │
│ │ Total  │ │ Online │ │ Offline│ │Mirror  │ │Known IPs│   │
│ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │
├──────────────────────────────────────────────────────────────┤
│ 📱 Devices │ 📡 Broadcast │ 📁 Groups │ 📊 Monitor          │
├──────────────────────────────────────────────────────────────┤
│ ┌──Samsung A54──┐ ┌──Xiaomi 13──┐ ┌──Pixel 8──┐           │
│ │ 🟢 ONLINE     │ │ 🟡 MIRROR   │ │ 🟢 ONLINE  │           │
│ │ 🔋 85%  🤖 14 │ │ 🔋 92% 🤖 13│ │ 🔋 67% 🤖 15│          │
│ │ ▶ [x]         │ │ ⏹ [x]      │ │ ▶ [x]     │           │
│ └───────────────┘ └─────────────┘ └───────────┘           │
│ ◀ Page 1/5 ▶              20 shown · 87 total              │
└──────────────────────────────────────────────────────────────┘
```

## ✨ Features

### 🚀 One-Click Install
- **`setup.bat`** — double-click, auto-installs Python + scrcpy + ADB + builds .exe
- **First launch** — auto-downloads scrcpy + ADB if missing
- Zero manual setup required

### 📱 Device Management
- **Auto-scan network** — scans subnet, auto-connects via ADB TCP/IP
- **Auto-pair** — sequential pairing, zero manual input
- **Auto-save IPs** — remembered and reconnected on next launch
- **Screen-off** (`-S`) — phone screen stays off while mirroring
- **Power-on-close** — phone screen turns on when window closes
- **USB + WiFi** — both modes supported

### 🎨 Modern UI
- **ttkbootstrap dark theme** — clean, modern, professional
- **9 theme options** — darkly, superhero, cyborg, solar, vapor, lumen, flatly, journal, morph
- **Device cards** — color-coded by status (green/red/amber)
- **Stats dashboard** — live Total/Online/Offline/Mirror/Known IPs

### 📊 Grid Pagination
- Configurable devices per page (default 20, max 100)
- ◀ Prev / Next ▶ navigation
- Multi-select checkboxes per device

### 📡 Broadcast
- Send ADB command to all/selected devices
- 8 preset commands (tap, swipe, home, back, power, volume, enter)
- File upload to all devices simultaneously

### 📁 Groups
- Create named device groups
- Drag devices between available/in-group

### 📊 Monitor
- Real-time health log (green terminal style)
- Exportable logs

### 🔋 Charge Mode
- Disables battery charging via ADB (≤5 devices only)
- Auto-disabled when more than 5 devices connected
- Saves USB port power

### ⚡ High FPS Support
- Default 30 FPS (smooth like phone screen)
- Configurable up to **240 FPS**
- Per-device bitrate control

---

## 🚀 Quick Start

### Windows (Recommended)

**Option 1 — One-Click Installer:**

1. Download `setup.bat` from this repo
2. Double-click it
3. Wait — it installs everything automatically
4. `scrcpy-farm.exe` appears on Desktop

**Option 2 — Manual:**

```powershell
git clone https://github.com/beytgoal/scrcpy-farm.git
cd scrcpy-farm
pip install pyinstaller ttkbootstrap
pyinstaller --onefile --noconsole --name "scrcpy-farm" scrcpy-farm.py
```

### Linux

```bash
git clone https://github.com/beytgoal/scrcpy-farm.git
cd scrcpy-farm
pip install ttkbootstrap
python3 scrcpy-farm.py
```

Or build binary:
```bash
chmod +x build/linux/build.sh
./build/linux/build.sh
```

### macOS

```bash
git clone https://github.com/beytgoal/scrcpy-farm.git
cd scrcpy-farm
pip install ttkbootstrap
python3 scrcpy-farm.py
```

Or build .app:
```bash
chmod +x build/macos/build.sh
./build/macos/build.sh
```

---

## 💻 USB Port Compatibility

### USB Standards vs Max Devices (per controller)

| USB Standard | Bandwidth | Max Stable Devices* | Recommended For |
|-------------|-----------|-------------------|-----------------|
| **USB 2.0** | 480 Mbps | 3-5 | Light monitoring |
| **USB 3.0** | 5 Gbps | 5-8 | Standard mirroring |
| **USB 3.1 Gen 2** | 10 Gbps | 8-12 | High-FPS mirroring |
| **USB 3.2 Gen 2x2** | 20 Gbps | 12-20 | Dense USB farms |
| **Thunderbolt 3/4** | 40 Gbps | 15-25 | Maximum USB density |

\* *Per USB controller. Most PCs have 2-4 controllers.*

### USB Connector Types

| Connector | Where | USB Standard | Use Case |
|-----------|-------|-------------|----------|
| **USB-A** | Desktop/Hub | 2.0 / 3.0 / 3.1 | Most common, backward compatible |
| **USB-C** | Modern PC/laptop | 3.1+ / Thunderbolt | Best bandwidth, reversible |
| **Micro-USB** | Older Android | USB 2.0 | ⚡ Slow, max 3-5 devices |
| **USB-C (device)** | Modern Android | USB 2.0-3.2 | Fastest when USB 3.2 capable |

### For 50-100+ Devices: Use WiFi

> ⚠️ **USB is not practical for 50+ devices.** Use TCP/IP + chargers instead.

| Hardware | Quantity | Purpose |
|----------|----------|---------|
| Multi-port USB charger (60-port) | 1-2 | Power all devices |
| WiFi 6 (AX) Access Points | 3-4 | ~30 devices per AP |
| Gigabit Ethernet Switch | 1 (48-port) | AP backbone |
| Any modern PC | 1 | Runs scrcpy-farm |

### Bandwidth Guide for Large Farms

| Devices | FPS | Bitrate/Device | Max Size | Total BW Needed |
|---------|-----|---------------|----------|----------------|
| 10 | 30 | 8M | 1280 | ~240 Mbps |
| 20 | 30 | 4M | 1024 | ~240 Mbps |
| 50 | 30 | 2M | 800 | ~300 Mbps |
| 100 | 15 | 1M | 720 | ~150 Mbps |
| 100 (eco) | 10 | 512K | 480 | ~50 Mbps |

---

## ⚙️ Settings

All settings stored in `~/.scrcpy-farm.json`.

| Setting | Default | Description |
|---------|---------|-------------|
| `scrcpy_path` | Platform-specific | Path to scrcpy binary |
| `adb_path` | Platform-specific | Path to ADB binary |
| `default_bitrate` | `4M` | Video bitrate per device |
| `default_max_size` | `1024` | Max video size (pixels) |
| `default_max_fps` | `30` | Max frames per second (1-240) |
| `default_screen_off` | `true` | Phone screen off when mirroring |
| `default_power_on_close` | `true` | Phone screen on when window closes |
| `grid_per_page` | `20` | Devices per grid page |
| `auto_scan` | `true` | Auto-scan subnet on startup |
| `auto_reconnect` | `true` | Reconnect saved devices |
| `subnet` | `192.168.1` | Subnet to scan |
| `charge_mode` | `false` | Disable ADB charging (≤5 devices) |
| `theme` | `darkly` | UI theme |

---

## 🧪 Project Structure

```
scrcpy-farm/
├── scrcpy-farm.py          # Main app (cross-platform, modern UI)
├── setup.bat               # Windows all-in-one installer
├── README.md               # This file
├── LICENSE                 # MIT
├── .gitignore
└── build/
    ├── windows/
    │   ├── build.bat       # Windows build script
    │   └── installer.iss   # Inno Setup script
    ├── linux/
    │   └── build.sh        # Linux build script
    └── macos/
        └── build.sh        # macOS build script
```

---

## 📋 Requirements

| Tool | Windows | Linux | macOS |
|------|---------|-------|-------|
| **Python 3.8+** | python.org | `sudo apt install python3` | `brew install python` |
| **ttkbootstrap** | `pip install ttkbootstrap` | `pip install ttkbootstrap` | `pip install ttkbootstrap` |
| **scrcpy** | Auto-download or [manual](https://github.com/Genymobile/scrcpy/releases/latest) | `sudo apt install scrcpy` | `brew install scrcpy` |
| **ADB** | Auto-download or [manual](https://developer.android.com/tools/releases/platform-tools) | `sudo apt install adb` | `brew install android-platform-tools` |

> 💡 **scrcpy and ADB are auto-downloaded on first launch if missing!**

---

## 📋 Changelog

### v4.0 (Current)
- **Modern UI** with ttkbootstrap (9 theme options)
- **Auto-download** scrcpy + ADB on first launch
- **One-click Windows installer** (`setup.bat`)
- **Max FPS increased** to 240 (default 30)
- Grid pagination (configurable 5-100 per page)
- Color-coded device cards with status indicators
- Stats dashboard (Total/Online/Offline/Mirror/Known IPs)
- Cross-platform: Windows, Linux, macOS

### v3.0
- Multi-device grid view
- Auto-scan + auto-save IPs
- Broadcast commands
- Device groups
- Health monitor

### v2.0
- Multi-device support
- TCP/IP connection manager

### v1.0
- Single-device mirroring

---

## 🤝 Contributing

1. Fork → Branch → PR
2. Test on at least one platform
3. Include screenshots for UI changes

---

## 📄 License

MIT — see [LICENSE](LICENSE)

Built on [scrcpy](https://github.com/Genymobile/scrcpy) by Genymobile.

---

*Made for Android device farms, testing labs, and developers managing many devices at once.*
