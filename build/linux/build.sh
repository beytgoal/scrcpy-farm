#!/bin/bash
# ================================================================
# SCRCPY-FARM BUILDER — Linux
# ================================================================
set -e

echo ""
echo "========================================"
echo "  scrcpy Farm — Linux Build"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Install it first:"
    echo "  sudo apt install python3 python3-pip python3-tk   (Debian/Ubuntu)"
    echo "  sudo pacman -S python python-pip python-tkinter     (Arch)"
    echo "  sudo dnf install python3 python3-pip python3-tkinter (Fedora)"
    exit 1
fi
echo "[1/3] ✅ Python3 $(python3 --version | cut -d' ' -f2)"

# Install PyInstaller
echo "[2/3] Installing PyInstaller..."
pip3 install --quiet --upgrade pip
pip3 install --quiet pyinstaller
echo "✅ PyInstaller ready"

# Compile
echo "[3/3] Compiling..."
cd "$SCRIPT_DIR/.."
pyinstaller --onefile --name "scrcpy-farm" scrcpy-farm.py

echo ""
echo "========================================"
echo "  ✅ DONE!"
echo "  Binary: dist/scrcpy-farm"
echo "  Run:    ./dist/scrcpy-farm"
echo "========================================"
echo ""
