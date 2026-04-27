# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Cinnamon panel applet for Linux Mint that displays the Logitech A20 X wireless headset battery percentage. Two components:

- **`battery_reader.py`** — Python script that reads battery level from the dongle and prints it to stdout
- **`applet.js`** — Cinnamon applet that runs the script every 20 minutes and displays the result in the panel

## Installing / testing

```bash
# Install applet (symlinks repo into Cinnamon's applet directory)
bash install.sh

# Install udev rule so the hidraw device is accessible without root
sudo cp 99-logitech-a20x.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw

# Test the battery reader directly (headset must be on, dongle plugged in)
python3 battery_reader.py
# → prints an integer 0–100, or ERROR: ... on failure
```

After changing `applet.js`, reload via: right-click panel → Applets → select the applet → restart (or `killall -HUP cinnamon`).

## How the battery protocol works

The A20 X dongle (USB ID `046d:0b35`) does **not** use standard HID++ 2.0. It exposes a firmware debug log ring buffer on HID report `0x07`, accessed via the `HIDIOCGFEATURE` ioctl (not interrupt reads/writes — plain `read()`/`write()` on the hidraw fd is silent).

Battery level appears in the log after each BLE connection event as the byte pattern:
```
05 5D 03 00 03 [pct%] [status]
```
where `status == 0x00` means charging. The log is a consuming ring buffer — each `HIDIOCGFEATURE` call advances the read pointer. Once drained, it returns all-zeros until new BLE events are logged.

`battery_reader.py` drains the log, scans backwards for the most recent battery entry, and caches the result to `/tmp/.a20x_battery_cache` (JSON, 2-hour TTL). The cache is the fallback when the log is empty (stable session with no recent BLE reconnects).

## Key constraints

- **Never send `HIDIOCSFEATURE` (SET) commands to the dongle from the applet.** Some SET commands trigger BLE disconnects, interrupting audio. The reader is intentionally read-only.
- The hidraw device number changes on each replug (`hidraw4`, `hidraw9`, etc.) — `find_hidraw()` discovers it dynamically via `/sys/class/hidraw/*/device/uevent`.
- A fresh battery reading only appears in the log after the headset BLE-connects to the dongle (typically at startup or after re-plugging). For long stable sessions the applet relies on the cache.
- The udev rule (`TAG+="uaccess"`) is required for non-root access; without it `systemd-logind` only grants the ACL at login time, not on replug.
