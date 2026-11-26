# KlipperScreen panel: belt tension by sound (camera microphone).
#
# Installed as a symlink: ~/KlipperScreen/panels/belt_freq.py -> this file
# (hidden from KlipperScreen's git via .git/info/exclude). Menu entry in KlipperScreen.conf:
#   [menu __main more belt_freq]  panel: belt_freq
#
# Views (Gtk.Stack):
#   overview - saved values per belt (tap a belt to measure it), group spread/advice,
#              Guided A/B, Measure pos, Setup pos
#   belt     - one belt only, big: live Hz, TIGHTEN/LOOSEN/OK, median. Opening a belt first moves
#              to its measuring position (A/B: X/Y from POS_FILE, Z belts: gantry height), then
#              listens (part fan + Nevermore off, restored when leaving)
#   check    - guided A/B result after each round: adjust and re-measure, or move the gantry
#              and re-check until two rounds in a row agree (belts settle after moving)
#   setup    - jog Y/Z and save the measuring positions (150 mm span)
# Target on a V2.4: A/B ~110 Hz over a 150 mm span, A/B within 2 Hz.
# Z belts: Voron docs start at ~140 Hz; the four should match each other (within ~2 Hz).
import json
import os
import signal
import statistics
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango
from ks_includes.screen_panel import ScreenPanel

SCRIPT = os.path.expanduser("~/printer_data/config/tools/belt_freq.py")
TARGET = 110.0
TOLERANCE = 5.0   # green within +-5 Hz of the target
MATCH = 2.0       # belts of one group (A/B, Z0-Z3) within this of each other
STABLE = 1.0      # guided: a belt is settled when two rounds differ by less than this
Z_TARGET = 140.0  # Voron docs: Z belts start at ~140 Hz (150 mm of the fixed side from the Z idler)
SLOTS = ("B", "A", "Z0", "Z1", "Z2", "Z3")   # B first: left as seen from the front
AB = ("B", "A")
# Fixed toolhead position for measuring, so every measurement uses the same belt span lengths.
# Voron: A/B span 150 mm = X/Y-joint idler centres 150 mm from the front idler centres.
POS_FILE = os.path.expanduser("~/printer_data/config/tools/belt_freq_pos.json")
SPAN = 150.0
# Front A/B span = toolhead Y + SPAN_OFFSET: the span grows 1:1 with Y. The offset is set by the
# front idler and X/Y-joint idler positions relative to Y0/the nozzle - the same parts on every
# V2.4 size. Measured on this V2.4 350 with a ruler 2026-11-26: 150 mm at Y105 -> 45 mm.
DEFAULT_SPAN_OFFSET = 45.0
DEFAULT_POS = (None, SPAN - DEFAULT_SPAN_OFFSET)   # X None = middle of the X axis (any bed size)
# Z belts (Voron docs): raise the gantry until the fixed side of the belt is 150 mm from the Z idler
# centres, ~140 Hz, all four equal. That height is not known until measured once with a ruler and
# stored with "Save Z" - until then the panel does not move Z (DEFAULT_Z is only a jog start value).
DEFAULT_Z = 60.0
GREEN, ORANGE, GREY = "#4caf50", "#ff9800", "#9e9e9e"


def load_pos():
    try:
        with open(POS_FILE) as f:
            d = json.load(f)
        return float(d["x"]), float(d["y"])
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULT_POS


def load_z():
    """(z, calibrated)"""
    try:
        with open(POS_FILE) as f:
            return float(json.load(f)["z"]), True
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULT_Z, False


def save_pos_file(**kw):
    try:
        with open(POS_FILE) as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    d.update(kw)
    with open(POS_FILE, "w") as f:
        json.dump(d, f)


def load_offset():
    try:
        with open(POS_FILE) as f:
            return float(json.load(f).get("span_offset", DEFAULT_SPAN_OFFSET))
    except (OSError, ValueError, AttributeError):
        return DEFAULT_SPAN_OFFSET


def target_of(slot):
    return Z_TARGET if slot.startswith("Z") else TARGET


def mk(text, size=None, color=None, bold=False):
    attrs = []
    if size:
        attrs.append(f'size="{size}"')
    if color:
        attrs.append(f'foreground="{color}"')
    if bold:
        attrs.append('weight="bold"')
    return f'<span {" ".join(attrs)}>{GLib.markup_escape_text(text)}</span>'


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
        self.last_msg = ""         # last non-protocol line from belt_freq.py (errors)
        self.current = None        # belt shown in the belt view
        self.guided = False
        self.round = 0
        self.rounds = []           # guided: list of {"B": f, "A": f, "moved": bool} per finished round
        self.moved = False         # guided: current round started with a gantry move

        self.stack = Gtk.Stack(vexpand=True)
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack.add_named(self._build_overview(), "overview")
        self.stack.add_named(self._build_belt(), "belt")
        self.stack.add_named(self._build_check(), "check")
        self.stack.add_named(self._build_setup(), "setup")
        self.content.add(self.stack)
        self._show_overview()

    # ---------- widgets ----------
    def _btn(self, label, style, cb, *args):
        """Text-only button with a fixed height (KlipperScreen buttons expand vertically and
        squeezed the lower rows on the 480 px screen)."""
        b = self._gtk.Button(None, label, style)
        b.set_vexpand(False)
        b.set_size_request(-1, 64)
        b.connect("clicked", cb, *args)
        return b

    @staticmethod
    def _label(wrap=True):
        lb = Gtk.Label(hexpand=True)
        lb.set_justify(Gtk.Justification.CENTER)
        if wrap:
            lb.set_line_wrap(True)
            lb.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        return lb

    def _build_overview(self):
        self.ov_info = self._label()
        self.slot_btns = {}
        grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=False, column_spacing=6, row_spacing=6)
        for i, k in enumerate(SLOTS):
            b = Gtk.Button(hexpand=True, can_focus=False)
            b.get_style_context().add_class("color1" if k in AB else "color4")
            lb = Gtk.Label()
            lb.set_justify(Gtk.Justification.CENTER)
            b.add(lb)
            b.connect("clicked", self.open_belt, k)
            self.slot_btns[k] = lb
            if k in AB:
                b.set_size_request(-1, 110)
                grid.attach(b, i * 2, 0, 2, 1)
            else:
                b.set_size_request(-1, 70)
                grid.attach(b, i - 2, 1, 1, 1)
        self.ov_groups = self._label()
        bottom = Gtk.Grid(column_homogeneous=True, column_spacing=6)
        bottom.attach(self._btn("Guided A/B", "color3", self.start_guided), 0, 0, 1, 1)
        bottom.attach(self._btn("Measure pos", "color2", self.goto_measure_pos), 1, 0, 1, 1)
        bottom.attach(self._btn("Setup pos", "color2", self.show_view, "setup"), 2, 0, 1, 1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, vexpand=True)
        box.pack_start(self.ov_info, False, False, 0)
        box.pack_start(grid, False, False, 0)
        box.pack_start(self.ov_groups, True, True, 0)
        box.pack_end(bottom, False, False, 0)
        return box

    def _build_belt(self):
        self.bt_title = self._label(False)
        self.bt_freq = self._label(False)
        self.bt_median = self._label()
        self.bt_hist = self._label()
        self.bt_info = self._label()
        self.bt_start = self._btn("Stop", "color3", self.toggle)
        self.bt_save = self._btn("Save", "color1", self.save_current)
        bottom = Gtk.Grid(column_homogeneous=True, column_spacing=6)
        bottom.attach(self.bt_start, 0, 0, 1, 1)
        bottom.attach(self._btn("Clear", "color2", self.clear), 1, 0, 1, 1)
        bottom.attach(self.bt_save, 2, 0, 1, 1)
        bottom.attach(self._btn("Back", "color4", self.leave_belt), 3, 0, 1, 1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, vexpand=True)
        box.pack_start(self.bt_title, False, False, 0)
        box.pack_start(self.bt_freq, True, True, 0)
        box.pack_start(self.bt_median, False, False, 0)
        box.pack_start(self.bt_hist, False, False, 0)
        box.pack_start(self.bt_info, False, False, 0)
        box.pack_end(bottom, False, False, 0)
        return box

    def _build_check(self):
        self.ck_title = self._label(False)
        self.ck_vals = self._label(False)
        self.ck_text = self._label()
        self.ck_adjust = self._btn("Adjust + measure", "color1", self.next_round, False)
        self.ck_move = self._btn("Move gantry + re-check", "color3", self.next_round, True)
        bottom = Gtk.Grid(column_homogeneous=True, column_spacing=6)
        bottom.attach(self.ck_adjust, 0, 0, 1, 1)
        bottom.attach(self.ck_move, 1, 0, 1, 1)
        bottom.attach(self._btn("Done", "color4", self.end_guided), 2, 0, 1, 1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, vexpand=True)
        box.pack_start(self.ck_title, False, False, 0)
        box.pack_start(self.ck_vals, True, True, 0)
        box.pack_start(self.ck_text, True, True, 0)
        box.pack_end(bottom, False, False, 0)
        return box

    def _build_setup(self):
        self.su_info = self._label()
        self.su_info.set_markup(
            "Set the measuring position once: jog Y until the X/Y-joint idler centres are\n"
            "<b>150 mm</b> from the front idler centres (ruler), then <b>Save pos</b>.")
        jog = Gtk.Grid(column_homogeneous=True, column_spacing=6, row_spacing=6)
        for i, d in enumerate((-10, -1, 1, 10)):
            jog.attach(self._btn(f"Y{d:+d}", "color3", self.jog, "Y", d), i, 0, 1, 1)
        for i, d in enumerate((-10, -1, 1, 10)):
            jog.attach(self._btn(f"Z{d:+d}", "color4", self.jog, "Z", d), i, 1, 1, 1)
        bottom = Gtk.Grid(column_homogeneous=True, column_spacing=6)
        bottom.attach(self._btn("Go Y pos", "color2", self.goto_measure_pos), 0, 0, 1, 1)
        bottom.attach(self._btn("Save Y", "color1", self.save_measure_pos), 1, 0, 1, 1)
        bottom.attach(self._btn("Go Z pos", "color2", self.goto_z_pos), 2, 0, 1, 1)
        bottom.attach(self._btn("Save Z", "color1", self.save_z_pos), 3, 0, 1, 1)
        bottom.attach(self._btn("Back", "color4", self.show_view, "overview"), 4, 0, 1, 1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True)
        box.pack_start(self.su_info, True, True, 0)
        box.pack_start(jog, False, False, 0)
        box.pack_end(bottom, False, False, 0)
        return box

    # ---------- view switching ----------
    def show_view(self, widget, name):
        if name == "overview":
            self._show_overview()
        else:
            if name == "setup":
                self._setup_text()
            self.stack.set_visible_child_name(name)

    def _setup_text(self, extra=""):
        x, y = self._pos()
        off = load_offset()
        z, cal = load_z()
        self.su_info.set_markup(
            (extra + "\n" if extra else "")
            + f"A/B: <b>X{x:.0f} Y{y:.0f}</b> = span {y + off:.0f} mm (span = Y + {off:.0f}).  "
            + (f"Z belts: <b>Z{z:.0f}</b>\n" if cal else "Z belts: <b>not set</b> - measure once\n")
            "The panel moves there automatically when you open a belt.\n"
            f"To change: jog until a ruler shows {SPAN:.0f} mm, then <b>Save Y</b> / <b>Save Z</b>.")

    def _show_overview(self, info=None):
        for k in SLOTS:
            v = self.saved[k]
            big = "x-large" if k in AB else "large"
            val = mk(f"{v:.1f} Hz", "large", self._color(v, k), True) if v else mk("tap to measure", "small", GREY)
            self.slot_btns[k].set_markup(f"{mk(k, big, bold=True)}\n{val}")
        self.ov_groups.set_markup(self._group(AB) + "\n" + self._group(("Z0", "Z1", "Z2", "Z3")))
        y = self._pos()[1]
        self.ov_info.set_markup(info or f"A/B target <b>{TARGET:.0f} Hz</b> at {y + load_offset():.0f} mm span "
                                        f"(Measure pos Y{y:.0f}), within {MATCH:.0f} Hz of each other. "
                                        f"Tap a belt, or use <b>Guided A/B</b>.")
        self.stack.set_visible_child_name("overview")

    # ---------- display helpers ----------
    @staticmethod
    def _color(f, slot="A"):
        return GREEN if abs(f - target_of(slot)) <= TOLERANCE else ORANGE

    @staticmethod
    def _word(f, slot):
        t = target_of(slot)
        if f < t - TOLERANCE:
            return "TIGHTEN", ORANGE
        if f > t + TOLERANCE:
            return "LOOSEN", ORANGE
        return "OK", GREEN

    def _group(self, keys):
        """One line per belt group: spread, and which belt to adjust."""
        vals = {k: self.saved[k] for k in keys if self.saved[k]}
        name = "A/B" if keys == AB else "Z"
        if len(vals) < 2:
            return mk(f"{name}: measure at least two belts to compare", color=GREY)
        spread = max(vals.values()) - min(vals.values())
        col = GREEN if spread <= MATCH else ORANGE
        txt = f'{name} spread <b><span foreground="{col}">{spread:.1f} Hz</span></b>'
        if spread > MATCH:
            ref = target_of(keys[0])
            far = max(vals, key=lambda k: abs(vals[k] - ref))
            goal = statistics.median([v for k, v in vals.items() if k != far])
            act = "tighten" if vals[far] < goal else "loosen"
            txt += f"  -  <b>{act} {far}</b> towards {goal:.1f} Hz"
        return txt

    def _update_belt(self):
        k = self.current
        good = [f for f, ok in self.plucks if ok]
        if good:
            m = statistics.median(good)
            word, col = self._word(m, k)
            self.bt_median.set_markup(
                f'Median <b><span foreground="{col}">{m:.1f} Hz  {word}</span></b>   '
                f'{m - target_of(k):+.1f} Hz vs target   ({len(good)} plucks)')
        else:
            self.bt_median.set_markup(mk("Pluck the belt in the middle of the span, ~1 s apart", color=GREY))
        last = self.plucks[-8:]
        self.bt_hist.set_markup("  ".join(f"{f:.1f}" if ok else mk(f"{f:.1f}?", color=GREY) for f, ok in last))

    # ---------- belt view ----------
    def open_belt(self, widget, slot, autostart=True):
        self.current = slot
        self.plucks = []
        rnd = f"   round {self.round}" if self.guided else ""
        prev = self.saved[slot]
        prev_txt = f"   last {prev:.1f} Hz" if prev else ""
        self.bt_title.set_markup(mk(f"Belt {slot}", "x-large", bold=True)
                                 + mk(f"   target {target_of(slot):.0f} Hz{rnd}{prev_txt}", "medium", GREY))
        self.bt_freq.set_markup(mk("---", "60000", GREY, True))
        self.bt_save.set_label("Save + next" if self.guided else "Save")
        self.bt_info.set_text("")
        self._update_belt()
        self.bt_start.set_label("Stop" if self.proc else "Start")
        self.stack.set_visible_child_name("belt")
        if autostart and not self.proc:
            self._goto_for(slot, self.start)

    def leave_belt(self, widget=None):
        if self.proc:
            self.stop()
        if self.guided:
            self.end_guided(None)
        else:
            self._show_overview()

    def save_current(self, widget):
        good = [f for f, ok in self.plucks if ok]
        if not good:
            self.bt_info.set_markup(mk("No plucks to save yet.", color=ORANGE))
            return
        k = self.current
        self.saved[k] = statistics.median(good)
        if self.proc:
            self.stop()
        if self.guided:
            i = AB.index(k)
            if i + 1 < len(AB):
                self.open_belt(None, AB[i + 1])
            else:
                self.rounds.append(dict({b: self.saved[b] for b in AB}, moved=self.moved))
                self._show_check()
        else:
            self._show_overview(f"Saved belt {k}: <b>{self.saved[k]:.1f} Hz</b>")

    # ---------- guided A/B ----------
    def start_guided(self, widget):
        self.guided = True
        self.round = 1
        self.rounds = []
        self.moved = False
        if self.proc:
            self.stop()
        self.open_belt(None, AB[0])

    def end_guided(self, widget):
        self.guided = False
        if self.proc:
            self.stop()
        self._show_overview("Guided A/B ended." if self.rounds else None)

    def _show_check(self):
        cur = self.rounds[-1]
        prev = self.rounds[-2] if len(self.rounds) > 1 else None
        spread = abs(cur["B"] - cur["A"])
        on_target = all(abs(v - TARGET) <= TOLERANCE for v in cur.values())
        matched = spread <= MATCH
        settled = prev is not None and cur["moved"] and all(abs(cur[b] - prev[b]) < STABLE for b in AB)
        lines = []
        for b in AB:
            v = cur[b]
            d = f"   ({v - prev[b]:+.1f})" if prev else ""
            lines.append(mk(f"{b}  {v:.1f} Hz", "x-large", self._color(v), True) + mk(d, "large", GREY))
        col = GREEN if matched else ORANGE
        lines.append(f'spread <b><span foreground="{col}">{spread:.1f} Hz</span></b> (max {MATCH:.0f})')
        self.ck_vals.set_markup("\n".join(lines))
        self.ck_title.set_markup(mk(f"Guided A/B - round {self.round} result", "large", bold=True))
        if on_target and matched and settled:
            text = mk("DONE - on target, matched and unchanged after moving the gantry.", "large", GREEN, True)
        elif on_target and matched:
            text = ("Looks good. Belts settle when the gantry moves:\n"
                    "<b>Move gantry + re-check</b> to confirm (moves Y away and back to the measuring position).")
        else:
            todo = []
            for b in AB:
                word, _ = self._word(cur[b], b)
                if word != "OK":
                    todo.append(f"<b>{word.lower()} {b}</b>")
            if not matched and not todo:
                far = max(AB, key=lambda b: abs(cur[b] - TARGET))
                other = AB[1 - AB.index(far)]
                todo.append(f"<b>{'tighten' if cur[far] < cur[other] else 'loosen'} {far}</b> towards {cur[other]:.1f} Hz")
            text = ("Adjust: " + ", ".join(todo) + " - small steps, the tensioners on both sides of a belt "
                    "by the same amount.\nThen <b>Adjust + measure</b> (or <b>Move gantry + re-check</b>).")
        self.ck_text.set_markup(text)
        self.stack.set_visible_child_name("check")

    def next_round(self, widget, move):
        self.round += 1
        self.moved = move
        if not move:
            self.open_belt(None, AB[0])
            return
        x, y = self._pos()
        home = "" if self._xy_homed() else "G28 X Y\n"
        # Move Y/X away so the belts redistribute tension, exactly like after a print; open_belt
        # then moves back to the measuring position and only starts listening once it stands still.
        # Distances scale with the bed and stay 10 mm inside the axis limits (any printer size).
        (x0, x1), (y0, y1) = self._limits("x"), self._limits("y")
        y_away = y + 0.4 * (y1 - y0) if y < (y0 + y1) / 2 else y - 0.4 * (y1 - y0)
        y_away = min(max(y_away, y0 + 10), y1 - 10)
        dx = min(0.25 * (x1 - x0), x - x0 - 10, x1 - 10 - x)
        self.open_belt(None, AB[0], autostart=False)
        self.bt_info.set_markup(mk("Moving the gantry away and back - wait...", color=ORANGE))
        self._screen._ws.klippy.gcode_script(
            f"{home}{self._safe_z()}G90\nG1 X{x:.1f} Y{y_away:.1f} F6000\nG1 X{x - dx:.1f} F6000\nG1 X{x + dx:.1f} F6000\nM400",
            self._moved, lambda: self._goto_for(AB[0], self.start))

    # ---------- position ----------
    def _limits(self, axis):
        """(min, max) of an axis from the printer config - works for any bed size."""
        sec = self._printer.get_config_section(f"stepper_{axis}") or {}
        try:
            return float(sec.get("position_min", 0)), float(sec["position_max"])
        except (KeyError, ValueError, TypeError):
            return 0.0, 250.0

    def _pos(self):
        """Measuring X/Y: saved, else X = middle of the axis; clamped to the axis limits."""
        x, y = load_pos()
        (x0, x1), (y0, y1) = self._limits("x"), self._limits("y")
        if x is None:
            x = (x0 + x1) / 2
        return min(max(x, x0), x1), min(max(y, y0), y1)

    def _goto_for(self, slot, after=None):
        """Move to the measuring position of this belt (A/B: X/Y, Z belts: gantry height), then
        call `after` once the move has finished (gcode M400 -> Moonraker replies afterwards).
        Listening only starts then, so motor noise is never taken as a pluck."""
        th = self._printer.get_stat("toolhead") or {}
        homed = th.get("homed_axes") or ""
        pos = th.get("position") or [None, None, None]
        if slot in AB:
            x, y = self._pos()
            if "x" in homed and "y" in homed and pos[0] is not None and \
                    abs(pos[0] - x) < 0.5 and abs(pos[1] - y) < 0.5:
                return after() if after else None
            script = ("" if "x" in homed and "y" in homed else "G28 X Y\n") + self._safe_z() + \
                f"G90\nG1 X{x} Y{y} F6000\nM400"
            where = f"X{x:.0f} Y{y:.0f} (span {y + load_offset():.0f} mm)"
        else:
            z, cal = load_z()
            if not cal:
                self.bt_info.set_markup(mk("Z measuring height not set: Setup pos -> jog Z until the fixed side is "
                                           "150 mm from the Z idler centres -> Save Z. Measuring here.", color=ORANGE))
                return after() if after else None
            if all(a in homed for a in "xyz") and pos[2] is not None and abs(pos[2] - z) < 0.5:
                return after() if after else None
            script = ("" if all(a in homed for a in "xyz") else "G28\n") + f"G90\nG1 Z{z} F900\nM400"
            where = f"Z{z:.0f}"
        self.bt_info.set_markup(mk(f"Moving to {where} - listening starts when it stops", color=ORANGE))
        self._screen._ws.klippy.gcode_script(script, self._moved, after)

    def _moved(self, result, method, params, after=None):
        if isinstance(result, dict) and "error" in result:
            msg = str(result["error"].get("message", result["error"]) if isinstance(result["error"], dict) else result["error"])
            self.bt_info.set_markup(mk(f"Move failed: {msg[:90]}", color=ORANGE))
            return
        if after and self.stack.get_visible_child_name() == "belt":
            after()

    def _safe_z(self):
        """Raise Z to 10 mm before XY moves if it is homed and lower (test prints on the bed)."""
        th = self._printer.get_stat("toolhead") or {}
        pos = th.get("position") or [0, 0, 99]
        return "G90\nG1 Z10 F600\n" if "z" in (th.get("homed_axes") or "") and pos[2] < 10 else ""

    def _xy_homed(self):
        homed = self._printer.get_stat("toolhead", "homed_axes") or ""
        return "x" in homed and "y" in homed

    def jog(self, widget, axis, d):
        """Small Y or Z steps to set up the measuring position (axis must be homed)."""
        homed = self._printer.get_stat("toolhead", "homed_axes") or ""
        if axis.lower() not in homed:
            self._setup_text(mk(f"Home {axis} first (Go {axis} pos homes it).", color=ORANGE))
            return
        f = 3000 if axis == "Y" else 600
        self._screen._ws.klippy.gcode_script(f"G91\nG1 {axis}{d} F{f}\nG90")
        pos = self._printer.get_stat("toolhead", "position") or [0, 0, 0]
        v = pos[1 if axis == "Y" else 2] + d
        if axis == "Y":
            self.su_info.set_markup(f"Y about <b>{v:.0f}</b> = span about <b>{v + load_offset():.0f} mm</b>.\n"
                                    f"If a ruler shows exactly {SPAN:.0f} mm here, press <b>Save Y</b>.")
        else:
            self.su_info.set_markup(f"Z about <b>{v:.0f}</b>.\nWhen the Z belt span is {SPAN:.0f} mm "
                                    f"(ruler, from the Z idler on the fixed side), press <b>Save Z</b>.")

    def save_measure_pos(self, widget):
        if not self._xy_homed():
            self.su_info.set_markup(mk("Home X/Y first.", color=ORANGE))
            return
        pos = self._printer.get_stat("toolhead", "position") or None
        if not pos:
            self.su_info.set_text("Toolhead position unknown.")
            return
        try:
            # Save Y means "the ruler shows SPAN here" -> also re-derive the offset
            save_pos_file(x=round(pos[0], 1), y=round(pos[1], 1), span_offset=round(SPAN - pos[1], 1))
            self._setup_text(f"Saved Y: <b>X{pos[0]:.1f} Y{pos[1]:.1f}</b> = {SPAN:.0f} mm span")
        except OSError as e:
            self.su_info.set_text(f"Could not save: {e}")

    def save_z_pos(self, widget):
        homed = self._printer.get_stat("toolhead", "homed_axes") or ""
        pos = self._printer.get_stat("toolhead", "position") or None
        if "z" not in homed or not pos:
            self._setup_text(mk("Home Z first (Go Z pos homes it).", color=ORANGE))
            return
        try:
            save_pos_file(z=round(pos[2], 1))
            self._setup_text(f"Saved Z: <b>Z{pos[2]:.1f}</b>")
        except OSError as e:
            self.su_info.set_text(f"Could not save: {e}")

    def goto_z_pos(self, widget):
        z, _ = load_z()
        homed = self._printer.get_stat("toolhead", "homed_axes") or ""
        script = "" if all(a in homed for a in "xyz") else "G28\n"
        self._screen._ws.klippy.gcode_script(f"{script}G90\nG1 Z{z} F900")
        self._setup_text(f"Moving to Z{z:.0f}")

    def goto_measure_pos(self, widget):
        """Move the toolhead to the saved measuring position (homes X/Y first if needed; Z is not moved)."""
        x, y = self._pos()
        script = "" if self._xy_homed() else "G28 X Y\n"
        self._screen._ws.klippy.gcode_script(f"{script}{self._safe_z()}G90\nG1 X{x} Y{y} F6000")
        msg = f"Moving to X{x:.0f} Y{y:.0f} - motors stay on (belts held) until the idle timeout."
        if self.stack.get_visible_child_name() == "setup":
            self.su_info.set_text(msg)
        else:
            self._show_overview(msg)

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
        return [n for n in ("heater_fan hotend_fan", "heater_fan controller_fan")
                if (self._printer.get_stat(n, "speed") or 0) > 0]

    def _fans_restore(self):
        for cmd in self.fan_restore:
            self._screen._ws.klippy.gcode_script(cmd)
        self.fan_restore = []

    # ---------- recording ----------
    def toggle(self, widget):
        if self.proc:
            self.stop()
        else:
            self.start()

    def clear(self, widget):
        self.plucks = []
        self.bt_freq.set_markup(mk("---", "60000", GREY, True))
        self._update_belt()

    def start(self):
        warm = self._fans_off()
        try:
            self.proc = subprocess.Popen(["/usr/bin/python3", "-u", SCRIPT, "--live"],
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as e:
            self.bt_info.set_text(f"Could not start: {e}")
            self._fans_restore()
            return
        self.partial = ""
        self.last_msg = ""
        self.watch = GLib.io_add_watch(self.proc.stdout, GLib.PRIORITY_DEFAULT,
                                       GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._on_output)
        self.bt_start.set_label("Stop")
        self.bt_info.set_markup(mk("Listening" + (" - heater fans running (noisy)" if warm else ""), color=GREY))

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
        self.bt_start.set_label("Start")
        if self.last_msg:   # keep the script's own message (e.g. no microphone) visible
            self.bt_info.set_markup(mk(f"Stopped: {self.last_msg}", color=ORANGE))
        else:
            self.bt_info.set_markup(mk("Not listening - press Start", color=GREY))

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
        if not parts or self.current is None:
            return
        if parts[0] == "PLUCK" and len(parts) == 4:
            f, ok = float(parts[1]), parts[3] == "1"
            self.plucks.append((f, ok))
            if ok:
                word, col = self._word(f, self.current)
                self.bt_freq.set_markup(mk(f"{f:.1f} Hz", "60000", col, True) + "\n" + mk(word, "xx-large", col, True))
            self._update_belt()
        elif parts[0] in ("LEVEL", "END"):
            pass
        elif parts[0] == "SOURCE":
            if parts[1] == "go2rtc":
                self.bt_info.set_markup(mk("Listening (mic shared with the webcam stream)", color=GREY))
        else:
            self.last_msg = line[:120]
            self.bt_info.set_text(self.last_msg)

    def deactivate(self):
        if self.proc:
            self.stop()
