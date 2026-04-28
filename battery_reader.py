#!/usr/bin/env python3
"""
Read Logitech A20 X headset battery via HID feature report debug log.

Output:
  PCT AGE_SECS CHARGING   — reading (AGE_SECS=0 if fresh, CHARGING=1 if on charge)
  DISCONNECTED            — headset BLE explicitly disconnected
  ERROR: reason           — dongle missing, permission denied, etc.
"""

import argparse
import fcntl
import glob
import json
import os
import sys
import time

VENDOR_ID = "046d"
PRODUCT_ID = "0b35"
PRODUCT_ID_WIRED = "0b2e"
CACHE_FILE = os.path.expanduser("~/.cache/a20x_battery_cache")
CACHE_MAX_AGE_SECS = 604800  # 7 days


def HIDIOCGFEATURE(n):
    return (3 << 30) | (ord("H") << 8) | 0x07 | (n << 16)


def find_hidraw(product_id=PRODUCT_ID):
    for uevent in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
        try:
            with open(uevent) as f:
                content = f.read().upper()
            if VENDOR_ID.upper() in content and product_id.upper() in content:
                dev = os.path.basename(os.path.dirname(os.path.dirname(uevent)))
                return f"/dev/{dev}"
        except OSError:
            pass
    return None


def read_log_chunks(fd, max_reads=30):
    all_data = bytearray()
    seen = set()
    for _ in range(max_reads):
        buf = bytearray(62)
        buf[0] = 0x07
        fcntl.ioctl(fd, HIDIOCGFEATURE(len(buf)), buf)
        valid_len = buf[1]
        if valid_len == 0:
            break
        chunk = bytes(buf[3:3 + valid_len])
        if chunk in seen:
            break
        seen.add(chunk)
        all_data.extend(chunk)
    return bytes(all_data)


def parse_log(data):
    """
    Walk log entries in order. Entry format: 05 [type] [len] 00 [len bytes].
    Returns (pct, charging, ble_connected) reflecting the most recent events seen.
    ble_connected is True/False if we saw a connect/disconnect; None if no BLE event.
    """
    pct = None
    charging = None
    ble_connected = None

    i = 0
    while i < len(data) - 4:
        if data[i] != 0x05:
            i += 1
            continue

        entry_type = data[i + 1]
        entry_len = data[i + 2]
        # data[i+3] is always 0x00 (padding/separator)

        if entry_len == 0 or i + 4 + entry_len > len(data):
            i += 1
            continue

        payload = data[i + 4: i + 4 + entry_len]

        if entry_type == 0x5D:
            if entry_len >= 3 and payload[0] == 0x03:
                # Battery notification: [0x03, pct, status]
                pct = payload[1]
                charging = (payload[2] == 0x00)
                ble_connected = True  # battery implies connected
            elif entry_len >= 2 and payload[0] == 0x92 and payload[1] == 0x0F:
                # Text log entry
                text = payload[2:].decode("ascii", errors="ignore")
                if "LE connected" in text:
                    ble_connected = True
                elif "LE disconnected" in text:
                    ble_connected = False
                    pct = None  # discard any battery from before disconnect

        i += 4 + entry_len

    return pct, charging, ble_connected


def load_cache():
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        age = int(time.time() - data.get("ts", 0))
        if age < CACHE_MAX_AGE_SECS:
            return data.get("pct"), data.get("charging", False), age, data.get("disconnected", False)
    except Exception:
        pass
    return None, None, 0, False


def save_cache(pct, charging):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({"pct": pct, "charging": charging, "ts": time.time()}, f)
    except Exception:
        pass


def save_disconnected():
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({"disconnected": True, "ts": time.time()}, f)
    except Exception:
        pass


def is_wired_charging():
    """Return True if the wired USB device is present and accessible (cable plugged in)."""
    wired_path = find_hidraw(PRODUCT_ID_WIRED)
    if not wired_path:
        return False
    try:
        fd = os.open(wired_path, os.O_RDWR)
        os.close(fd)
        return True
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Print raw log bytes and parsed events")
    args = parser.parse_args()

    path = find_hidraw()
    if not path:
        print("ERROR: A20 X dongle not found")
        sys.exit(1)

    try:
        fd = os.open(path, os.O_RDWR)
    except PermissionError:
        print("ERROR: Permission denied")
        sys.exit(1)

    wired = is_wired_charging()
    if args.debug:
        print(f"[debug] wired={wired}", file=sys.stderr)

    try:
        log_data = read_log_chunks(fd)
        if args.debug:
            print(f"[debug] dongle log ({len(log_data)} bytes): {log_data.hex()}", file=sys.stderr)
        pct, charging, ble_connected = parse_log(log_data)
        if args.debug:
            print(f"[debug] dongle parse: pct={pct} charging={charging} ble_connected={ble_connected}", file=sys.stderr)

        # Approach 1: probe the wired USB device's own log buffer (read-only, no side effects)
        if pct is None and wired:
            wired_path = find_hidraw(PRODUCT_ID_WIRED)
            if args.debug:
                print(f"[debug] probing wired device {wired_path}", file=sys.stderr)
            try:
                wfd = os.open(wired_path, os.O_RDWR)
                try:
                    wired_log = read_log_chunks(wfd)
                finally:
                    os.close(wfd)
                if args.debug:
                    print(f"[debug] wired log ({len(wired_log)} bytes): {wired_log.hex()}", file=sys.stderr)
                if wired_log:
                    p, c, _ = parse_log(wired_log)
                    if args.debug:
                        print(f"[debug] wired parse: pct={p} charging={c}", file=sys.stderr)
                    if p is not None:
                        pct, charging = p, True
            except OSError as e:
                if args.debug:
                    print(f"[debug] wired open failed: {e}", file=sys.stderr)

    finally:
        os.close(fd)

    if pct is not None:
        effective_charging = wired or charging
        save_cache(pct, effective_charging)
        print(f"{pct} 0 {1 if effective_charging else 0}")
        return

    if ble_connected is False:
        # Explicit disconnect seen in log with no subsequent reconnect
        save_disconnected()
        print("DISCONNECTED")
        return

    # No fresh data — fall back to cache
    cached_pct, cached_charging, age_secs, cached_disconnected = load_cache()
    if cached_disconnected:
        print("DISCONNECTED")
        return
    if cached_pct is not None:
        effective_charging = wired or cached_charging
        print(f"{cached_pct} {age_secs} {1 if effective_charging else 0}")
        return

    print("ERROR: No data — turn headset off/on to get first reading")
    sys.exit(1)


if __name__ == "__main__":
    main()
