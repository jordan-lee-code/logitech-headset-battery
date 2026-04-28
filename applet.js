const Applet = imports.ui.applet;
const GLib = imports.gi.GLib;
const Gio = imports.gi.Gio;
const St = imports.gi.St;

const UUID = "logitech-headset-battery@local";
const UPDATE_INTERVAL_SECS = 5;
const LOW_BATTERY_THRESHOLD = 20;

const COLOR_GOOD = "battery-good";
const COLOR_WARN = "battery-warn";
const COLOR_CRITICAL = "battery-critical";
const COLOR_UNKNOWN = "battery-unknown";

function LogitechBatteryApplet(metadata, orientation, panel_height, instance_id) {
    this._init(metadata, orientation, panel_height, instance_id);
}

LogitechBatteryApplet.prototype = {
    __proto__: Applet.Applet.prototype,

    _init: function(metadata, orientation, panel_height, instance_id) {
        Applet.Applet.prototype._init.call(this, orientation, panel_height, instance_id);

        this._scriptPath = metadata.path + "/battery_reader.py";
        this._timer = 0;
        this._lastBatteryLevel = null;

        this.setAllowedLayout(Applet.AllowedLayout.BOTH);

        this._icon = new St.Icon({
            icon_name: "audio-headphones-symbolic",
            icon_type: St.IconType.SYMBOLIC,
            icon_size: 16,
            style_class: "applet-icon"
        });

        this._label = new St.Label({
            text: "--",
            style_class: "applet-label"
        });

        this.actor.add(this._icon, { y_align: St.Align.MIDDLE, y_fill: false });
        this.actor.add(this._label, { y_align: St.Align.MIDDLE, y_fill: false });

        this.set_applet_tooltip("Logitech headset battery");
        this._refresh();
    },

    _clearColors: function() {
        this._label.remove_style_class_name(COLOR_GOOD);
        this._label.remove_style_class_name(COLOR_WARN);
        this._label.remove_style_class_name(COLOR_CRITICAL);
        this._label.remove_style_class_name(COLOR_UNKNOWN);
    },

    _setColor: function(colorClass) {
        this._clearColors();
        this._label.add_style_class_name(colorClass);
    },

    _notifyLowBattery: function(level) {
        if (this._lastBatteryLevel !== null &&
            this._lastBatteryLevel > LOW_BATTERY_THRESHOLD &&
            level <= LOW_BATTERY_THRESHOLD) {
            GLib.spawn_command_line_async(
                'notify-send -u critical -i battery-caution ' +
                '"Headset Battery Low" ' +
                '"Logitech A20 X is at ' + level + '% — plug in soon"'
            );
        }
        this._lastBatteryLevel = level;
    },

    _updateDisplay: function(output) {
        output = output.trim();

        if (!output || output.startsWith("ERROR")) {
            this._label.set_text("N/A");
            this._setColor(COLOR_UNKNOWN);
            this._icon.set_icon_name("audio-headphones-symbolic");
            this.set_applet_tooltip(output || "No output from battery reader");
            return;
        }

        if (output === "DISCONNECTED") {
            this._label.set_text("off");
            this._setColor(COLOR_UNKNOWN);
            this._icon.set_icon_name("audio-headphones-symbolic");
            this.set_applet_tooltip("Headset off or out of range\n(Click to refresh)");
            return;
        }

        // Format: PCT AGE_SECS CHARGING
        const parts = output.split(" ");
        const level = parseInt(parts[0], 10);
        const ageSecs = parts.length > 1 ? parseInt(parts[1], 10) : 0;
        const charging = parts.length > 2 && parts[2] === "1";

        if (isNaN(level) || level < 0 || level > 100) {
            this._label.set_text("?");
            this._setColor(COLOR_UNKNOWN);
            this.set_applet_tooltip("Unexpected output: " + output);
            return;
        }

        this._notifyLowBattery(level);

        this._label.set_text(charging ? "⚡" : level + "%");

        if (charging) {
            this._setColor(COLOR_GOOD);
        } else if (level > 50) {
            this._setColor(COLOR_GOOD);
        } else if (level > LOW_BATTERY_THRESHOLD) {
            this._setColor(COLOR_WARN);
        } else {
            this._setColor(COLOR_CRITICAL);
        }

        let ageStr;
        if (ageSecs < 60) {
            ageStr = "just now";
        } else if (ageSecs < 3600) {
            ageStr = Math.floor(ageSecs / 60) + " min ago";
        } else {
            ageStr = Math.floor(ageSecs / 3600) + " hr ago";
        }

        const chargingStr = charging ? "charging" : "on battery";
        this.set_applet_tooltip(
            "Logitech A20 X: " + level + "% (" + chargingStr + ")\n" +
            "Reading: " + ageStr + "\n" +
            "(Click to refresh)"
        );
    },

    _refresh: function() {
        this._stopTimer();

        let proc;
        try {
            proc = Gio.Subprocess.new(
                ["python3", this._scriptPath],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
            );
        } catch(e) {
            global.logError(UUID + ": failed to start battery_reader.py: " + e);
            this._label.set_text("Err");
            this._setColor(COLOR_UNKNOWN);
            this._startTimer();
            return;
        }

        proc.communicate_utf8_async(null, null, (proc, result) => {
            try {
                let [ok, stdout] = proc.communicate_utf8_finish(result);
                this._updateDisplay(ok ? (stdout || "") : "ERROR: subprocess failed");
            } catch(e) {
                global.logError(UUID + ": " + e);
                this._updateDisplay("ERROR: " + e);
            }
            this._startTimer();
        });
    },

    _startTimer: function() {
        this._stopTimer();
        this._timer = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            UPDATE_INTERVAL_SECS,
            () => {
                this._refresh();
                return GLib.SOURCE_REMOVE;
            }
        );
    },

    _stopTimer: function() {
        if (this._timer > 0) {
            GLib.source_remove(this._timer);
            this._timer = 0;
        }
    },

    on_applet_clicked: function() {
        this._refresh();
    },

    on_applet_removed_from_panel: function() {
        this._stopTimer();
    }
};

function main(metadata, orientation, panel_height, instance_id) {
    return new LogitechBatteryApplet(metadata, orientation, panel_height, instance_id);
}
