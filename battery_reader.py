#!/usr/bin/env python3
"""Read Logitech A20 X headset battery level via HID++ 2.0."""

import glob
import os
import select
import sys
import time

VENDOR_ID = "046d"
PRODUCT_ID = "0b35"  # A20 X wireless dongle
SW_ID = 0x01
LONG_REPORT = 0x11
LONG_REPORT_SIZE = 20
FEATURE_UNIFIED_BATTERY = 0x1004
FEATURE_BATTERY_STATUS = 0x1000


def find_hidraw_devices():
    devices = []
    for uevent_path in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
        try:
            with open(uevent_path) as f:
                content = f.read().upper()
            if VENDOR_ID.upper() in content and PRODUCT_ID.upper() in content:
                hidraw_dir = os.path.dirname(os.path.dirname(uevent_path))
                dev_name = os.path.basename(hidraw_dir)
                devices.append(f"/dev/{dev_name}")
        except OSError:
            pass
    return devices


def build_msg(device_idx, feature_idx, func_idx, params=b""):
    msg = bytearray(LONG_REPORT_SIZE)
    msg[0] = LONG_REPORT
    msg[1] = device_idx
    msg[2] = feature_idx
    msg[3] = ((func_idx & 0x0F) << 4) | SW_ID
    for i, b in enumerate(params[:16]):
        msg[4 + i] = b
    return bytes(msg)


def send_recv(fd, msg, device_idx, timeout=2.0):
    try:
        os.write(fd, msg)
    except OSError:
        return None
    end = time.monotonic() + timeout
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return None
        r, _, _ = select.select([fd], [], [], remaining)
        if not r:
            return None
        try:
            resp = os.read(fd, LONG_REPORT_SIZE)
        except OSError:
            return None
        if len(resp) < 4:
            continue
        # Match device index and SW_ID in low nibble of byte 3
        if (resp[0] in (0x10, 0x11)
                and resp[1] == device_idx
                and (resp[3] & 0x0F) == SW_ID):
            if resp[2] == 0xFF:  # error response feature index
                return None
            return resp


def query_battery(fd, device_idx):
    for feat_code, func_idx in [
        (FEATURE_UNIFIED_BATTERY, 1),   # getStatus() returns SoC at byte 4
        (FEATURE_BATTERY_STATUS, 0),    # getBatteryLevelStatus() returns level at byte 4
    ]:
        params = bytes([feat_code >> 8, feat_code & 0xFF])
        resp = send_recv(fd, build_msg(device_idx, 0x00, 0x00, params), device_idx)
        if resp is None or resp[4] == 0:
            continue
        feat_idx = resp[4]
        resp = send_recv(fd, build_msg(device_idx, feat_idx, func_idx), device_idx)
        if resp is not None:
            return resp[4]
    return None


def main():
    paths = find_hidraw_devices()
    if not paths:
        print("ERROR: A20 X dongle not found")
        sys.exit(1)

    for path in paths:
        try:
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError:
            print("ERROR: Permission denied - run install.sh to set up udev rule")
            sys.exit(1)
        except OSError:
            continue

        try:
            for device_idx in (0xFF, 0x01):
                level = query_battery(fd, device_idx)
                if level is not None:
                    print(level)
                    return
        finally:
            os.close(fd)

    print("ERROR: Battery feature not supported")
    sys.exit(1)


if __name__ == "__main__":
    main()
