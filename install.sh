#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
APPLET_UUID="logitech-headset-battery@local"
APPLET_DIR="$HOME/.local/share/cinnamon/applets/$APPLET_UUID"
UDEV_RULE_DEST="/etc/udev/rules.d/99-logitech-a20x.rules"

echo "=== Logitech Headset Battery Applet Installer ==="
echo ""

# Symlink applet directory
mkdir -p "$(dirname "$APPLET_DIR")"
if [ -L "$APPLET_DIR" ]; then
    rm "$APPLET_DIR"
elif [ -d "$APPLET_DIR" ]; then
    echo "WARNING: $APPLET_DIR exists and is not a symlink — backing up to ${APPLET_DIR}.bak"
    mv "$APPLET_DIR" "${APPLET_DIR}.bak"
fi
ln -sf "$REPO_DIR" "$APPLET_DIR"
echo "Applet symlinked: $APPLET_DIR → $REPO_DIR"

# Install udev rule
echo "Installing udev rule (requires sudo)..."
sudo cp "$REPO_DIR/99-logitech-a20x.rules" "$UDEV_RULE_DEST"
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
echo "udev rule installed at $UDEV_RULE_DEST"

echo ""
echo "=== Next steps ==="
echo ""
echo "1. Re-plug the USB dongle (or restart) so the new udev rule takes effect."
echo ""
echo "2. Test the battery reader:"
echo "   python3 $REPO_DIR/battery_reader.py"
echo ""
echo "3. Enable the applet in Cinnamon:"
echo "   Right-click the panel → Applets → find 'Logitech Headset Battery' → Add to Panel"
echo ""
