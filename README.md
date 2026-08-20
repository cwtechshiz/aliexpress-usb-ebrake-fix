# aliexpress-usb-ebrake-fix

A Linux workaround for cheap USB sim-racing e-brake levers that show up as:

```
Bus 003 Device 006: ID 1eaf:0024 Leaflabs Maple
```

On Windows these work as an analog slider that also fires a digital button
at full pull. On Linux (confirmed on CachyOS/KDE), only the button comes
through — no analog input at all, at any point in the pull range.

## Root cause

The device is actually built around a **WCH CH551G** microcontroller (an
8051-core USB MCU), not a real LeafLabs Maple — the firmware just reuses
LeafLabs' USB vendor/product ID, likely copied from an old example
project. Confirmed via the chip markings and `usbhid-dump`.

Its HID report descriptor declares **two analog Slider fields using the
identical HID usage code**:

```
0x09, 0x36,   // Usage (Slider)   <- always reports 0, unused
0x09, 0x36,   // Usage (Slider)   <- this is the e-brake's real value
```

Windows' HID stack tracks report fields by position, so both surface fine
as separate axes. Linux's generic HID→evdev mapping (`hid-input.c`) maps
by usage code, and when it hits the second identical `Slider` usage
(already claimed by the first field), it silently drops it instead of
assigning a new axis. Confirmed with `hid-recorder`: the raw report bytes
for the second Slider field track the lever position smoothly the whole
way through — the signal is genuinely there, it just never reaches
evdev/`ABS_THROTTLE`.

This is a Linux kernel HID-input mapping bug, not a hardware fault or a
firmware bug. It's been reported upstream (see [Reporting upstream]
(#reporting-upstream) below) but until/unless it's fixed in the kernel,
this repo works around it in userspace.

## What this does

`ebrakefix.py` reads the raw HID reports straight from `/dev/hidraw*`
(via `hid-recorder`, from the `hid-tools` package), pulls out the second
Slider value, and re-emits it as a proper analog axis (`ABS_THROTTLE`) on
a new virtual joystick called **`ebrake-fixed`**, created via `uinput`.
Games, Steam, and Proton/SDL2 all read this exactly like any other
joystick.

A udev rule starts it automatically (via systemd) every time the e-brake
is plugged in, and a second udev rule tags the virtual device as a
joystick so it also shows up in desktop tools like KDE's
Settings → Game Controller panel.

## The "real" fix

The CH551G has a factory USB bootloader and can be reflashed on Linux
with open tools like [`isp55e0`](https://github.com/frank-zago/isp55e0)
or `chprog`. Giving the second Slider field its own distinct usage code
(e.g. `Dial` or `Wheel` instead of a duplicate `Slider`) would fix this
natively on every OS, no workaround needed. That's a project for another
day — this repo is the no-reflash stopgap in the meantime.

## Install

Requires `hid-tools` (for `hid-recorder`) and Python 3 with `pip`.

```bash
git clone <this-repo-url>
cd aliexpress-usb-ebrake-fix
sudo ./install.sh
```

This installs:

| File | Installed to | Purpose |
|---|---|---|
| `ebrakefix.py` | `/usr/local/bin/ebrakefix.py` | the fix itself |
| `ebrake-fix.service` | `/etc/systemd/system/` | runs the script |
| `99-ebrake-autostart.rules` | `/etc/udev/rules.d/` | starts the service on plug-in |
| `99-ebrake-joystick.rules` | `/etc/udev/rules.d/` | tags the virtual device as a joystick |

After installing, unplug and replug the e-brake — it should just work
from then on, every boot, every plug-in, with no manual steps.

## Verifying it worked

```bash
systemctl status ebrake-fix.service
ls /dev/input/js*
jstest /dev/input/jsN     # pick whichever index is "ebrake-fixed"
```

Pull the lever slowly — the axis value should move smoothly across the
full range with no dead zones or jumps.

## Calibrating

```bash
sudo jscal -c /dev/input/jsN
```

Then bind the analog axis (not the button) to your e-brake in your sim's
control settings — it will show up as `ebrake-fixed` in the device list.

## Uninstalling

```bash
sudo systemctl stop ebrake-fix.service
sudo rm /usr/local/bin/ebrakefix.py
sudo rm /etc/systemd/system/ebrake-fix.service
sudo rm /etc/udev/rules.d/99-ebrake-autostart.rules
sudo rm /etc/udev/rules.d/99-ebrake-joystick.rules
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
```

## Reporting upstream

If you hit this on a different device with the same symptom (analog axis
works on Windows, only a button shows on Linux), it's worth reporting to
the kernel HID maintainers — this is a general `hid-input.c` bug (silently
dropping a report field when two fields share a usage code), not specific
to this one board. Useful evidence to include:

- `sudo usbhid-dump -d <vid>:<pid> -e descriptor`
- a `hid-recorder` capture while operating the control through its full
  range
- `evtest` output showing the axis is missing despite the above

File at [bugzilla.kernel.org](https://bugzilla.kernel.org) (Drivers → HID)
or email `linux-input@vger.kernel.org`.
