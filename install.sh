#!/usr/bin/env bash
# install.sh - aliexpress-usb-ebrake-fix
#
# Installs the e-brake fix script, systemd service, and udev rules so the
# analog axis works automatically every time the device is plugged in.
#
# Run from inside the repo directory:
#   sudo ./install.sh

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run this with sudo: sudo ./install.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Checking dependencies (python3-uinput, hid-tools)..."
if ! python3 -c "import uinput" >/dev/null 2>&1; then
  echo "    python-uinput not found, installing with pip..."
  pip install --break-system-packages python-uinput
fi
if ! command -v hid-recorder >/dev/null 2>&1; then
  echo "!! hid-recorder not found on PATH. Install the 'hid-tools' package"
  echo "   for your distro before using this fix (e.g. 'sudo pacman -S hid-tools')."
fi

echo "==> Installing ebrakefix.py to /usr/local/bin/"
install -m 755 "$SCRIPT_DIR/ebrakefix.py" /usr/local/bin/ebrakefix.py

echo "==> Installing systemd service"
install -m 644 "$SCRIPT_DIR/ebrake-fix.service" /etc/systemd/system/ebrake-fix.service

echo "==> Installing udev rules"
install -m 644 "$SCRIPT_DIR/99-ebrake-autostart.rules" /etc/udev/rules.d/99-ebrake-autostart.rules
install -m 644 "$SCRIPT_DIR/99-ebrake-joystick.rules" /etc/udev/rules.d/99-ebrake-joystick.rules

echo "==> Reloading udev and systemd"
udevadm control --reload-rules
udevadm trigger
systemctl daemon-reload

echo ""
echo "Done. Unplug and replug the e-brake (or run:"
echo "  sudo systemctl start ebrake-fix.service"
echo "to start it immediately without replugging)."
echo ""
echo "Check status with:"
echo "  systemctl status ebrake-fix.service"
echo "  ls /dev/input/js*"
