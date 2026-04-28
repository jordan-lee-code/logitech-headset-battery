# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Cinnamon panel applet for Linux Mint that displays the Logitech A20 X wireless headset battery percentage. Two components:

- **`battery_reader.py`** — Python script that reads battery level from the dongle and prints it to stdout
- **`applet.js`** — Cinnamon applet that runs the script every 60 seconds and displays the result in the panel

## Installing / testing

```bash
# Install applet (symlinks repo into Cinnamon's applet directory)
bash install.sh

# Install udev rules so hidraw devices are accessible without root
sudo cp 99-logitech-a20x.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw

# Test the battery reader directly (headset must be on, dongle plugged in)
python3 battery_reader.py
# → "PCT AGE_SECS CHARGING", "DISCONNECTED", or "ERROR: ..."
```

After changing `applet.js`, reload via: `Alt+F2` → type `r` → Enter (restarts Cinnamon in place). Simply clicking the applet only refreshes the data, not the JS.

## How the battery protocol works

The A20 X dongle (USB ID `046d:0b35`) does **not** use standard HID++ 2.0. It exposes a firmware debug log ring buffer on HID report `0x07`, accessed via the `HIDIOCGFEATURE` ioctl (not interrupt reads/writes — plain `read()`/`write()` on the hidraw fd is silent).

Battery level appears in the log after each BLE connection event:
```
05 5D 03 00 03 [pct%] [status]
```
where `status == 0x00` means charging, `0x01` means on battery.

Text log entries have the form:
```
05 5D [len] 00 92 0F [ASCII text]
```
Known text entries: `"LE connected"`, `"LE disconnected"`, `"media state: PLAYING/PAUSED"`, `"Start scanning"`, `"Stop scan"`, `"Coordinated set size[1]"`. Mute state and volume level are **not** logged.

The log is a consuming ring buffer — each `HIDIOCGFEATURE` call advances the read pointer. Once drained it returns `valid_len == 0` until new BLE events are logged.

`battery_reader.py` drains the log, parses entries in order (last battery/disconnect wins), and caches the result to `~/.cache/a20x_battery_cache` (JSON, 7-day TTL).

## Charging detection

Two signals, OR'd together:

1. **Wired USB device present** (`046d:0b2e`, hidraw with `HID_NAME=Logitech A20 X - USB wired mode`) — opening this device succeeds only when a data-capable USB cable is connected
2. **BLE log charging flag** — `status == 0x00` in a battery log entry

Charge-only USB connections (power bank, charger, charge-only cable) do not enumerate the `0b2e` device and produce no log entries, so they cannot be detected.

## udev rules

`99-logitech-a20x.rules` covers both devices:
- `0b35` (wireless dongle): `TAG+="uaccess"` — relies on systemd-logind granting the session user an ACL
- `0b2e` (wired USB mode): `GROUP="plugdev", MODE="0660"` — `uaccess` tag alone does not reliably apply the ACL on hotplug for this device; group-based rule is used instead

## Key constraints

- **Never send `HIDIOCSFEATURE` (SET) commands to the dongle.** Commands `[0x02, 0x04, 0x00]` and `[0x0d, 0x1d]` trigger BLE disconnects, interrupting audio. The reader is intentionally read-only.
- The hidraw device number changes on each replug — `find_hidraw()` discovers it dynamically via `/sys/class/hidraw/*/device/uevent`.
- A fresh battery reading only appears in the log after a BLE reconnect. For long stable sessions the applet relies on the cache.
