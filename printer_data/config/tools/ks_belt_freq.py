# KlipperScreen panel: belt tension by sound (camera microphone).
#
# Installed as a symlink: ~/KlipperScreen/panels/belt_freq.py -> this file
# (hidden from KlipperScreen's git via .git/info/exclude). Menu entry in KlipperScreen.conf:
#   [menu __main more belt_freq]  panel: belt_freq
#
# Start: part fan + Nevermore off, runs tools/belt_freq.py --live and shows every pluck.
# Stop:  ends the recording and restores the fans. A / B store the current median so the
# two belts can be compared. Target on a V2.4: ~110 Hz over a 150 mm span, A/B within 2 Hz.
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


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "Belt tension"
        super().__init__(screen, title)
        self.proc = None
        self.watch = None
        self.partial = ""
        self.plucks = []
        self.saved = {"A": None, "B": None}
        self.fan_restore = []

        self.freq = Gtk.Label(hexpand=True)
        self.freq.set_markup(self._big("---"))
        self.info = Gtk.Label(label=f"Target {TARGET:.0f} Hz (150 mm span). Press Start, pluck the belt.",
                              hexpand=True, wrap=True)
        self.median = Gtk.Label(hexpand=True)
        self.history = Gtk.Label(hexpand=True, wrap=True)
        self.ab = Gtk.Label(hexpand=True)
        self._update_ab()

        self.start_btn = self._gtk.Button("resume", "Start", "color3")
        self.start_btn.connect("clicked", self.toggle)
        clear = self._gtk.Button("refresh", "Clear", "color2")
        clear.connect("clicked", self.clear)
        save_a = self._gtk.Button(None, "Save A", "color1")
        save_a.connect("clicked", self.save, "A")
        save_b = self._gtk.Button(None, "Save B", "color4")
        save_b.connect("clicked", self.save, "B")

        buttons = Gtk.Grid(column_homogeneous=True, vexpand=False)
        buttons.attach(self.start_btn, 0, 0, 1, 1)
        buttons.attach(clear, 1, 0, 1, 1)
        buttons.attach(save_a, 2, 0, 1, 1)
        buttons.attach(save_b, 3, 0, 1, 1)

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

    def _update_ab(self):
        a, b = self.saved["A"], self.saved["B"]
        txt = "A: " + (f"{a:.1f} Hz" if a else "-") + "    B: " + (f"{b:.1f} Hz" if b else "-")
        if a and b:
            d = a - b
            col = "#4caf50" if abs(d) <= 2 else "#ff9800"
            txt += f'    <span foreground="{col}">A-B {d:+.1f} Hz</span>'
        self.ab.set_markup(txt)

    def _update_results(self):
        good = [f for f, ok in self.plucks if ok]
        if good:
            m = statistics.median(good)
            self.median.set_markup(f'Median <b><span foreground="{self._color(m)}">{m:.1f} Hz</span></b>'
                                   f'  ({len(good)} plucks, {min(good):.1f}-{max(good):.1f})'
                                   f'  {m - TARGET:+.1f} Hz vs target')
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
        self.info.set_text(f"Saved belt {which}. Measure the other belt and save it too.")

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
                self.freq.set_markup(self._big(f"{f:.1f} Hz", self._color(f)))
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
