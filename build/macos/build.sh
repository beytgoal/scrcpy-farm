#!/bin/bash
# ================================================================
# SCRCPY-FARM BUILDER — macOS
# ================================================================
set -e

echo ""
echo "========================================"
echo "  scrcpy Farm — macOS Build"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Install it:"
    echo "  brew install python-tk"
    exit 1
fi
echo "[1/3] ✅ Python3 $(python3 --version | cut -d' ' -f2)"

# Install PyInstaller
echo "[2/3] Installing PyInstaller..."
pip3 install --quiet --upgrade pip
pip3 install --quiet pyinstaller
echo "✅ PyInstaller ready"

# Compile
echo "[3/3] Compiling as .app bundle..."
cd "$SCRIPT_DIR/.."
pyinstaller --onefile --windowed --name "scrcpy-farm" scrcpy-farm.py

echo ""
echo "========================================"
echo "  ✅ DONE!"
echo "  App: dist/scrcpy-farm.app"
echo "  (or dist/scrcpy-farm for CLI)"
echo "========================================"
echo ""
