#!/usr/bin/env bash
# Setup PX4 SITL in WSL2 Ubuntu for ProjectWyvern testing.
# Run from WSL: bash scripts/setup-px4-sitl.sh
#
# This takes ~20-30 minutes on first run (clones PX4, installs deps, builds).
# Subsequent runs skip completed steps.

set -euo pipefail

PX4_DIR="$HOME/PX4-Autopilot"

echo "=== Step 1: System dependencies ==="
sudo apt-get update -qq
sudo apt-get install -y -qq git make cmake python3-pip python3-venv \
    gcc g++ ninja-build astyle libxml2-dev libxslt-dev \
    wget curl unzip > /dev/null

echo "=== Step 2: Clone PX4 ==="
if [ -d "$PX4_DIR" ]; then
    echo "PX4 already cloned at $PX4_DIR, pulling latest..."
    cd "$PX4_DIR" && git pull --ff-only || true
else
    git clone https://github.com/PX4/PX4-Autopilot.git "$PX4_DIR" --recursive --depth 1
fi

echo "=== Step 3: PX4 dependencies ==="
cd "$PX4_DIR"
bash Tools/setup/ubuntu.sh --no-nuttx

echo "=== Step 4: Build PX4 SITL (headless, no Gazebo) ==="
cd "$PX4_DIR"
make px4_sitl_default boardconfig < /dev/null || true
HEADLESS=1 make px4_sitl none_iris -j$(nproc) || {
    echo "Build failed. Trying with fewer jobs..."
    HEADLESS=1 make px4_sitl none_iris -j2
}

echo "=== Step 5: Install mavsdk Python in WSL ==="
pip3 install --user mavsdk fastapi uvicorn httpx

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start PX4 SITL (headless, no Gazebo):"
echo "  cd ~/PX4-Autopilot && make px4_sitl none_iris"
echo ""
echo "To start PX4 SITL with Gazebo (if installed):"
echo "  cd ~/PX4-Autopilot && make px4_sitl gz_x500"
echo ""
echo "PX4 SITL listens on UDP 14540 for MAVSDK connections."
