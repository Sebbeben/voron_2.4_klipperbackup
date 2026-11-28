# KlipperScreen panel: belt tension by sound (camera microphone).
#
# Installed as a symlink: ~/KlipperScreen/panels/belt_freq.py -> this file
# (hidden from KlipperScreen's git via .git/info/exclude). Menu entry in KlipperScreen.conf:
#   [menu __main more belt_freq]  panel: belt_freq
#
# Start: part fan + Nevermore off, runs tools/belt_freq.py --live and shows every pluck.
# Stop:  ends the recording and restores the fans. A / B / Z0-Z3 store the current median so
# the belts can be compared. Target on a V2.4: A/B ~110 Hz over a 150 mm span, A/B within 2 Hz.
# Z belts: Voron docs start at ~140 Hz; the four should match each other (within ~2 Hz).
import json
import os
import signal
import statistics
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from ks_includes.screen_panel import ScreenPanel

SCRIPT = os.path.expanduser("~/printer_data/config/tools/belt_freq.py")
TARGET = 110.0
TOLERANCE = 5.0   # green within +-5 Hz of the target
MATCH = 2.0       # belts of one group (A/B, Z0-Z3) within this of each other
Z_TARGET = 140.0  # Voron docs: Z belts start at ~140 Hz (150 mm of the fixed side from the Z idler)
SLOTS = ("B", "A", "Z0", "Z1", "Z2", "Z3")   # B first: left as seen from the front
# Fixed toolhead position for measuring, so every measurement uses the same belt span lengths.
# Voron: A/B span 150 mm = X/Y-joint idler centres 150 mm from the front idler centres.
# Set it once on the panel (jog Y, measure with a ruler, "Save pos"); stored in POS_FILE.
POS_FILE = os.path.expanduser("~/printer_data/config/tools/belt_freq_pos.json")
DEFAULT_POS = (175.0, 175.0)


def load_pos():
    try:
        with open(POS_FILE) as f:
            d = json.load(f)
        return float(d["x"]), float(d["y"])
    except (OSError, ValueError, KeyError):
        return DEFAULT_POS


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "Belt tension"
        super().__init__(screen, title)
        self.proc = None
        self.watch = None
        self.partial = ""
        self.plucks = []
        self.saved = {k: None for k in SLOTS}
        self.fan_restore = []

        self.freq = Gtk.Label(hexpand=True)
        self.freq.set_justify(Gtk.Justification.CENTER)
        self.freq.set_markup(self._big("---"))
        self.info = Gtk.Label(label=f"Target {TARGET:.0f} Hz (150 mm span). Press Start, pluck the belt.",
                              hexpand=True, wrap=True)
        self.median = Gtk.Label(hexpand=True)
        self.history = Gtk.Label(hexpand=True, wrap=True)
        self.ab = Gtk.Label(hexpand=True, wrap=True)
        self._update_ab()

        self.start_btn = self._gtk.Button("resume", "Start", "color3")
        self.start_btn.connect("clicked", self.toggle)
        clear = self._gtk.Button("refresh", "Clear", "color2")
        clear.connect("clicked", self.clear)
        goto = self._gtk.Button("move", "Measure pos", "color2")
        goto.connect("clicked", self.goto_measure_pos)
        jog = []
        for d in (-10, -1, 1, 10):
            b = self._gtk.Button(None, f"Y{d:+d}", "color3")
            b.connect("clicked", self.jog_y, d)
            jog.append(b)
        save_pos = self._gtk.Button(None, "Save pos", "color2")
        save_pos.connect("clicked", self.save_measure_pos)

        buttons = Gtk.Grid(column_homogeneous=True, vexpand=False)
        buttons.attach(self.start_btn, 0, 0, 2, 1)
        buttons.attach(clear, 2, 0, 2, 1)
        buttons.attach(goto, 4, 0, 2, 1)
        for i, b in enumerate(jog):
            buttons.attach(b, i, 1, 1, 1)
        buttons.attach(save_pos, 4, 1, 2, 1)
        for i, k in enumerate(SLOTS):
            b = self._gtk.Button(None, f"Save {k}", "color1" if k in ("B", "A") else "color4")
            b.connect("clicked", self.save, k)
            buttons.attach(b, i, 2, 1, 1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, vexpand=True)
        box.pack_start(self.freq, True, True, 0)
        box.pack_start(self.median, False, False, 0)
        box.pack_start(self.history, False, False, 0)
        box.pack_start(self.ab, False, False, 0)
        box.pack_start(self.info, False, False, 0)
        box.pack_end(buttons, False, False, 0)
        self.content.add(box)

    # ---------- display helpers ----------
    @staticmethod
    def _big(text, color="white"):
        return f'<span size="xx-large" weight="bold" foreground="{color}">{text}</span>'

    @staticmethod
    def _color(f):
        return "#4caf50" if abs(f - TARGET) <= TOLERANCE else "#ff9800"

    @staticmethod
    def _advice(f):
        # Frequency rises with the square root of the tension: +10 % tension ~ +5 % frequency.
        if f < TARGET - TOLERANCE:
            return '<b><span foreground="#ff9800">TIGHTEN</span></b> (too loose)'
        if f > TARGET + TOLERANCE:
            return '<b><span foreground="#ff9800">LOOSEN</span></b> (too tight)'
        return '<b><span foreground="#4caf50">OK</span></b>'

    def _group(self, keys, use_target):
        """One line per belt group: saved values, spread, and which belt to adjust."""
        vals = {k: self.saved[k] for k in keys if self.saved[k]}
        txt = "  ".join(f"{k}: " + (f"{self.saved[k]:.1f}" if self.saved[k] else "-") for k in keys)
        if len(vals) < 2:
            return txt
        spread = max(vals.values()) - min(vals.values())
        col = "#4caf50" if spread <= MATCH else "#ff9800"
        txt += f'   <span foreground="{col}">spread {spread:.1f} Hz</span>'
        if spread > MATCH:
            # A/B: adjust the belt furthest from the target. Z: no target - adjust the belt
            # furthest from the median of the group towards it.
            ref = TARGET if use_target else Z_TARGET
            far = max(vals, key=lambda k: abs(vals[k] - ref))
            others = [v for k, v in vals.items() if k != far]
            goal = statistics.median(others)
            act = "tighten" if vals[far] < goal else "loosen"
            txt += f'\n<b>{act} {far}</b> towards {goal:.1f} Hz'
        return txt

    def _update_ab(self):
        self.ab.set_markup(self._group(("B", "A"), True) + "\n" + self._group(("Z0", "Z1", "Z2", "Z3"), False))

    def _update_results(self):
        good = [f for f, ok in self.plucks if ok]
        if good:
            m = statistics.median(good)
            self.median.set_markup(f'Median <b><span foreground="{self._color(m)}">{m:.1f} Hz</span></b>'
                                   f'  ({len(good)} plucks, {min(good):.1f}-{max(good):.1f})'
                                   f'  {m - TARGET:+.1f} Hz vs target\n{self._advice(m)}')
        else:
            self.median.set_text("")
        last = self.plucks[-8:]
        self.history.set_markup("  ".join(f"{f:.1f}" if ok else f'<span foreground="grey">{f:.1f}?</span>'
                                          for f, ok in last))

    # ---------- buttons ----------
    def toggle(self, widget):
        if self.proc:
            self.stop()
        else:
            self.start()

    def clear(self, widget):
        self.plucks = []
        self.freq.set_justify(Gtk.Justification.CENTER)
        self.freq.set_markup(self._big("---"))
        self._update_results()

    def save(self, widget, which):
        good = [f for f, ok in self.plucks if ok]
        if not good:
            self.info.set_text("No plucks to save yet.")
            return
        self.saved[which] = statistics.median(good)
        self._update_ab()
        self.clear(None)
        self.info.set_text(f"Saved belt {which}." + (f" Z: ~{Z_TARGET:.0f} Hz and match the four belts (the big A/B advice does not apply)."
                                                     if which.startswith("Z") else ""))

    def _xy_homed(self):
        homed = self._printer.get_stat("toolhead", "homed_axes") or ""
        return "x" in homed and "y" in homed

    def jog_y(self, widget, d):
        """Move Y in small steps to set up the 150 mm span (needs X/Y homed; Z is not moved)."""
        if not self._xy_homed():
            self.info.set_text("Home X/Y first (press Measure pos).")
            return
        self._screen._ws.klippy.gcode_script(f"G91\nG1 Y{d} F3000\nG90")
        pos = self._printer.get_stat("toolhead", "position") or [0, 0]
        self.info.set_text(f"Y about {pos[1] + d:.0f}. Aim: X/Y idler centres 150 mm from the front idler centres, then Save pos.")

    def save_measure_pos(self, widget):
        if not self._xy_homed():
            self.info.set_text("Home X/Y first.")
            return
        pos = self._printer.get_stat("toolhead", "position") or None
        if not pos:
            self.info.set_text("Toolhead position unknown.")
            return
        try:
            with open(POS_FILE, "w") as f:
                json.dump({"x": round(pos[0], 1), "y": round(pos[1], 1)}, f)
            self.info.set_text(f"Measure position saved: X{pos[0]:.1f} Y{pos[1]:.1f}")
        except OSError as e:
            self.info.set_text(f"Could not save: {e}")

    def goto_measure_pos(self, widget):
        """Move the toolhead to the saved measuring position (homes X/Y first if needed; Z is not moved)."""
        x, y = load_pos()
        homed = self._printer.get_stat("toolhead", "homed_axes") or ""
        script = "" if ("x" in homed and "y" in homed) else "G28 X Y\n"
        self._screen._ws.klippy.gcode_script(f"{script}G90\nG1 X{x} Y{y} F6000")
        self.info.set_text(f"Moving to X{x} Y{y} - motors stay on (belts held) until the idle timeout.")

    # ---------- fans ----------
    def _fans_off(self):
        self.fan_restore = []
        part = self._printer.get_stat("fan", "speed") or 0
        if part > 0:
            self.fan_restore.append(f"M106 S{round(part * 255)}")
            self._screen._ws.klippy.gcode_script("M107")
        nev = self._printer.get_stat("fan_generic nevermore", "speed") or 0
        if nev > 0:
            self.fan_restore.append(f"SET_FAN_SPEED FAN=nevermore SPEED={nev:.2f}")
            self._screen._ws.klippy.gcode_script("SET_FAN_SPEED FAN=nevermore SPEED=0")
        warm = [n for n in ("heater_fan hotend_fan", "heater_fan controller_fan")
                if (self._printer.get_stat(n, "speed") or 0) > 0]
        return warm

    def _fans_restore(self):
        for cmd in self.fan_restore:
            self._screen._ws.klippy.gcode_script(cmd)
        self.fan_restore = []

    # ---------- recording ----------
    def start(self):
        warm = self._fans_off()
        try:
            self.proc = subprocess.Popen(["/usr/bin/python3", "-u", SCRIPT, "--live"],
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as e:
            self.info.set_text(f"Could not start: {e}")
            self._fans_restore()
            return
        self.partial = ""
        self.watch = GLib.io_add_watch(self.proc.stdout, GLib.PRIORITY_DEFAULT,
                                       GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._on_output)
        self.start_btn.set_label("Stop")
        msg = "Listening - pluck the belt (same spot, ~1 s apart)."
        if warm:
            msg += " Heater fans running: noisy."
        self.info.set_text(msg)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
        self._finish()

    def _finish(self):
        if self.watch:
            GLib.source_remove(self.watch)
            self.watch = None
        if self.proc:
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
        self._fans_restore()
        self.start_btn.set_label("Start")
        self.info.set_text("Stopped. Fans restored.")

    def _on_output(self, source, condition):
        if condition & GLib.IO_IN:
            data = os.read(self.proc.stdout.fileno(), 4096).decode(errors="replace")
            if data:
                lines = (self.partial + data).split("\n")
                self.partial = lines.pop()
                for line in lines:
                    self._handle(line.strip())
                return True
        # EOF / error: the script ended (time limit or failure)
        self.watch = None
        self._finish()
        return False

    def _handle(self, line):
        parts = line.split()
        if not parts:
            return
        if parts[0] == "PLUCK" and len(parts) == 4:
            f, ok = float(parts[1]), parts[3] == "1"
            self.plucks.append((f, ok))
            if ok:
                word = "OK" if abs(f - TARGET) <= TOLERANCE else ("tighten" if f < TARGET else "loosen")
                self.freq.set_markup(self._big(f"{f:.1f} Hz", self._color(f))
                                     + f'\n<span size="large">{word}</span>')
            self._update_results()
        elif parts[0] == "LEVEL":
            pass
        elif parts[0] == "SOURCE":
            if parts[1] == "go2rtc":
                self.info.set_text("Listening (mic shared with the webcam stream) - pluck the belt.")
        elif parts[0] != "END":
            self.info.set_text(line[:120])

    def deactivate(self):
        if self.proc:
            self.stop()
