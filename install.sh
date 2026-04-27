#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
APPLET_UUID="logitech-headset-battery@local"
APPLET_DIR="$HOME/.local/share/cinnamon/applets/$APPLET_UUID"
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
echo ""
echo "Note: hidraw access is granted automatically by systemd-logind — no udev rule needed."

echo ""
echo "=== Next steps ==="
echo ""
echo "1. Test the battery reader (headset must be on):"
echo "   python3 $REPO_DIR/battery_reader.py"
echo ""
echo "2. Enable the applet in Cinnamon:"
echo "   Right-click the panel → Applets → find 'Logitech Headset Battery' → Add to Panel"
echo ""
