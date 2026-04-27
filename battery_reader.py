#!/usr/bin/env python3
"""
Read Logitech A20 X headset battery via HID feature report debug log.

The dongle exposes a debug log ring buffer on report 0x07 (HIDIOCGFEATURE).
Battery level appears as the pattern: 05 5d 03 00 03 [pct%] [status]
after each BLE connection event. We read the log passively (no disruptive
commands) and cache the last known value to handle stable sessions where
the BLE doesn't reconnect.
"""

import fcntl
import glob
import json
import os
import sys
import time

VENDOR_ID = "046d"
PRODUCT_ID = "0b35"
CACHE_FILE = "/tmp/.a20x_battery_cache"
CACHE_MAX_AGE_SECS = 3600  # show cached value for up to 1 hour


def HIDIOCGFEATURE(n):
    return (3 << 30) | (ord("H") << 8) | 0x07 | (n << 16)


def find_hidraw():
    for uevent in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
        try:
            with open(uevent) as f:
                content = f.read().upper()
            if VENDOR_ID.upper() in content and PRODUCT_ID.upper() in content:
                dev = os.path.basename(os.path.dirname(os.path.dirname(uevent)))
                return f"/dev/{dev}"
        except OSError:
            pass
    return None


def read_log_chunks(fd, max_reads=30):
    """Drain all available log data from the ring buffer."""
    all_data = bytearray()
    seen = set()
    for _ in range(max_reads):
        buf = bytearray(62)
        buf[0] = 0x07
        fcntl.ioctl(fd, HIDIOCGFEATURE(len(buf)), buf)
        valid_len = buf[1]
        if valid_len == 0:
            break
        chunk = bytes(buf[3 : 3 + valid_len])
        if chunk in seen:
            break
        seen.add(chunk)
        all_data.extend(chunk)
    return bytes(all_data)


def find_battery(data):
    """
    Scan for battery entry pattern in the log data.
    Pattern: 05 5d 03 00 03 [pct] [status]
    Returns (pct, charging_bool) or (None, None).
    """
    # Walk backwards so we get the most recent entry
    for i in range(len(data) - 6, -1, -1):
        if (
            data[i] == 0x05
            and data[i + 1] == 0x5D
            and data[i + 2] == 0x03
            and data[i + 3] == 0x00
            and data[i + 4] == 0x03
        ):
            pct = data[i + 5]
            charging = data[i + 6] == 0x00
            return pct, charging
    return None, None


def load_cache():
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        age = time.time() - data.get("ts", 0)
        if age < CACHE_MAX_AGE_SECS:
            return data.get("pct"), data.get("charging")
    except Exception:
        pass
    return None, None


def save_cache(pct, charging):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"pct": pct, "charging": charging, "ts": time.time()}, f)
    except Exception:
        pass


def main():
    path = find_hidraw()
    if not path:
        print("ERROR: A20 X dongle not found")
        sys.exit(1)

    try:
        fd = os.open(path, os.O_RDWR)
    except PermissionError:
        print("ERROR: Permission denied")
        sys.exit(1)

    try:
        log_data = read_log_chunks(fd)
    finally:
        os.close(fd)

    pct, charging = find_battery(log_data)

    if pct is not None:
        save_cache(pct, charging)
        print(pct)
        return

    # No fresh data — fall back to cache
    cached_pct, _ = load_cache()
    if cached_pct is not None:
        print(cached_pct)
        return

    print("ERROR: No battery data (re-plug dongle for first reading)")
    sys.exit(1)


if __name__ == "__main__":
    main()
