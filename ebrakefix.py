#!/usr/bin/env python3
"""
aliexpress-usb-ebrake-fix
--------------------------
Workaround for cheap USB e-brake levers (WCH CH551-based, USB ID 1eaf:0024,
enumerates as "LeafLabs Maple") whose HID report descriptor declares two
analog Slider fields with the SAME HID usage code. Windows' HID stack
surfaces both fields fine, but Linux's hid-input usage-mapping only keeps
one axis per usage code and silently drops the second -- which is the
e-brake's actual analog value. Only the full-pull button survives.

This script reads the raw HID reports (via hid-recorder, from the
`hid-tools` package) and re-emits the second Slider value as a proper
analog axis on a new virtual joystick via uinput, called "ebrake-fixed".

Root cause + real fix: the device firmware (a WCH CH551) can be reflashed
to give the second Slider field its own distinct usage code, which fixes
this natively on every OS. This script is the no-reflash workaround.
See README.md for details.
"""

import glob
import re
import subprocess
import sys
import time

import uinput

# Match the USB vendor/product ID for the device (LeafLabs Maple VID:PID,
# reused by this board's firmware).
VENDOR_ID = "1EAF"
PRODUCT_ID = "0024"

# hid-recorder prints parsed report lines like:
#   #              | X:   512 | Y:   512 | Rx:     0 | Ry:     0 | Slider:     0 ,   128
# The SECOND number after "Slider:" is the e-brake's analog value.
SLIDER_RE = re.compile(r"Slider:\s*(-?\d+)\s*,\s*(-?\d+)")

AXIS_MIN = 0
AXIS_MAX = 1023


def find_hidraw():
    """Locate the /dev/hidraw* node for the e-brake by vendor/product ID."""
    for path in glob.glob("/sys/class/hidraw/hidraw*"):
        try:
            with open(f"{path}/device/uevent") as f:
                uevent = f.read().upper()
        except FileNotFoundError:
            continue
        if VENDOR_ID in uevent and PRODUCT_ID in uevent:
            return "/dev/" + path.split("/")[-1]
    return None


def wait_for_device(poll_seconds=1):
    dev = find_hidraw()
    while not dev:
        time.sleep(poll_seconds)
        dev = find_hidraw()
    return dev


def main():
    dev = find_hidraw() if len(sys.argv) < 2 else sys.argv[1]
    if not dev:
        print("Waiting for e-brake device...", flush=True)
        dev = wait_for_device()

    print(f"Using hidraw device: {dev}", flush=True)

    events = [
        uinput.ABS_THROTTLE + (AXIS_MIN, AXIS_MAX, 0, 0),
        uinput.BTN_TRIGGER,  # placeholder button so joydev creates /dev/input/jsN
    ]

    with uinput.Device(events, name="ebrake-fixed") as vjoy:
        vjoy.emit(uinput.BTN_TRIGGER, 0, syn=True)

        proc = subprocess.Popen(
            ["stdbuf", "-oL", "hid-recorder", dev],
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        print("Reading reports, forwarding axis to 'ebrake-fixed'. Ctrl+C to stop.", flush=True)
        try:
            for line in proc.stdout:
                match = SLIDER_RE.search(line)
                if match:
                    value = int(match.group(2))
                    value = max(AXIS_MIN, min(AXIS_MAX, value))
                    vjoy.emit(uinput.ABS_THROTTLE, value)
        except KeyboardInterrupt:
            pass
        finally:
            proc.terminate()


if __name__ == "__main__":
    main()
