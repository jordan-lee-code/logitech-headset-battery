# Logitech Headset Battery

A Cinnamon panel applet for Linux Mint that displays the Logitech A20 X wireless headset battery percentage.

![Panel showing headset icon and battery percentage]

## Requirements

- Linux Mint with Cinnamon desktop
- Logitech A20 X wireless headset + USB dongle (USB ID `046d:0b35`)
- Python 3

## Installation

```bash
git clone https://github.com/jordan-lee-code/logitech-headset-battery.git
cd logitech-headset-battery
bash install.sh
```

Then install the udev rule so the dongle is accessible without root:

```bash
sudo cp 99-logitech-a20x.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw
```

Finally, enable the applet: **right-click the panel → Applets → Logitech Headset Battery → Add to Panel**.

## Usage

- Battery percentage is shown in the panel next to a headphone icon
- Colour coding: green (>50%), yellow (20–50%), red (<20%)
- Updates every 20 minutes, or click the applet to refresh immediately
- The first reading appears after the headset connects to the dongle — if the panel shows `--` on first load, wait a few seconds and click to refresh

## How it works

The A20 X dongle exposes a firmware debug log via a HID feature report. Battery level is logged after each BLE connection between the dongle and headset. `battery_reader.py` reads this log passively (no commands sent to the dongle) and caches the last known value for up to 2 hours to handle stable sessions.
