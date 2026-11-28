"""Shared helpers for the calibration gcode generators (gen_flow_tiles.py, ...).

Remote-friendly test prints: every test is placed on a free spot of the bed so the
next test can run without clearing the plate. Kept free at all times:
  - QGL probe points and the Z home point (bed centre, Tap probe at nozzle)
  - the PRINT_START prime line strip at the front (Y 4, X 125-225)
  - the KOMB brush area at the rear
Used areas are recorded in bed_layout.json; run `gen_flow_tiles.py --reset-layout`
(or delete the file) after the plate has been cleared.
"""
import json, math, os, time

BED_X, BED_Y = 350.0, 350.0
LAYOUT_FILE = os.environ.get("CALIB_LAYOUT") or os.path.expanduser("~/printer_data/config/tools/bed_layout.json")
FIL_AREA = math.pi * (1.75 / 2) ** 2
# QGL travels between probe points at horizontal_move_z 10 - the toolhead/duct passes over
# most of the bed, so remote tests must stay well below that.
MAX_REMOTE_HEIGHT = 6.0
# The duct/toolhead extends ~30 mm around the nozzle and sits only a few mm above the tip.
# Printing (and bed_mesh at horizontal_move_z 2) next to a taller earlier test makes the duct
# hit it - Tap then reports "Probe triggered prior to movement" (2026-11-26). Keep this much
# clearance to any test taller than LOW_HEIGHT.
DUCT_CLEARANCE = 35.0
LOW_HEIGHT = 1.5

# Points where Tap probes down to the bed: QGL corners and the Z home (bed centre)
PROBE_POINTS = [(50, 25), (50, 275), (300, 275), (300, 25), (175, 175)]

# Keep-out rectangles (x0, y0, x1, y1)
KEEP_OUT = [
    (50 - 18, 25 - 18, 50 + 18, 25 + 18),       # QGL points (probe offset 0)
    (50 - 18, 275 - 18, 50 + 18, 275 + 18),
    (300 - 18, 275 - 18, 300 + 18, 275 + 18),
    (300 - 18, 25 - 18, 300 + 18, 25 + 18),
    (175 - 25, 175 - 25, 175 + 25, 175 + 25),   # Z home (G28 Z at bed centre)
    (110, 0, 240, 14),                          # PRINT_START prime line
    (0, 330, BED_X, BED_Y),                     # rear: park position, KOMB brush
    (0, 0, BED_X, 10), (0, 0, 10, BED_Y), (BED_X - 10, 0, BED_X, BED_Y),  # edges
]


def e_per_mm(width, height, flow):
    """Slic3r/Orca extrusion cross-section (rectangle with round ends)."""
    area = (width - height) * height + math.pi * (height / 2) ** 2
    return area / FIL_AREA * flow


def spacing(width, height):
    """Slic3r/Orca centre-to-centre spacing for adjacent extrusions."""
    return width - height * (1 - math.pi / 4)


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def load_layout():
    try:
        return json.load(open(LAYOUT_FILE))
    except (OSError, ValueError):
        return []


def reset_layout():
    if os.path.exists(LAYOUT_FILE):
        os.remove(LAYOUT_FILE)


def find_spot(w, h, height, margin=5.0):
    """First free (x0, y0) for a w x h footprint, scanning front-left to rear-right.
    Tall neighbours (or a tall new test) need DUCT_CLEARANCE instead of margin."""
    tall = [r["name"] for r in load_layout() if r.get("height", 0) > MAX_REMOTE_HEIGHT]
    if tall:
        raise SystemExit(f"{tall[0]} is taller than {MAX_REMOTE_HEIGHT} mm - QGL would hit it. "
                         "Clear the plate and run with --reset-layout first.")
    used = []
    if height > LOW_HEIGHT:          # the duct comes down to the bed at every probe point
        for px, py in PROBE_POINTS:
            c = DUCT_CLEARANCE - margin
            used.append((px - c, py - c, px + c, py + c))
    for r in load_layout():
        m = DUCT_CLEARANCE if max(r.get("height", MAX_REMOTE_HEIGHT), height) > LOW_HEIGHT else margin
        x0, y0, x1, y1 = r["rect"]
        used.append((x0 - m + margin, y0 - m + margin, x1 + m - margin, y1 + m - margin))
    y = 10.0
    while y + h <= BED_Y:
        x = 10.0
        while x + w <= BED_X:
            r = (x - margin, y - margin, x + w + margin, y + h + margin)
            if not any(_overlap(r, k) for k in KEEP_OUT + used):
                return x, y
            x += 5.0
        y += 5.0
    raise SystemExit("No free spot on the bed - clear the plate and run with --reset-layout")


def record(rect, name, height):
    lay = load_layout()
    lay.append({"name": name, "rect": [round(v, 1) for v in rect], "height": round(height, 2),
                "time": time.strftime("%Y-%m-%d %H:%M")})
    json.dump(lay, open(LAYOUT_FILE, "w"), indent=1)


def start_gcode(bed, temp, purge_x0, purge_y, purge_len=60.0, obj_xy=None):
    """Home, QGL, Z home, adaptive mesh (KAMP, objects must be defined before), purge.
    Does not use PRINT_START (its fixed prime line would print on top of earlier ones)."""
    ox, oy = obj_xy if obj_xy else (purge_x0, purge_y + 10)
    purge_e = purge_len * 0.5 / FIL_AREA        # 0.5 mm2 cross-section (limit 0.64)
    return f"""M140 S{bed}
M104 S150                       ; warm, non-oozing nozzle for Tap
SET_IDLE_TIMEOUT TIMEOUT=1800
G90
M83
G28
M190 S{bed}
M109 S150
KOMB                            ; brush the nozzle before Tap probes (plastic on the tip = wrong Z)
BED_MESH_CLEAR
QUAD_GANTRY_LEVEL
G28 Z
G1 Z10 F600                     ; bed_mesh travels at horizontal_move_z 2 -
G1 X{ox:.1f} Y{oy:.1f} F12000   ; start it over this test's own (empty) area
BED_MESH_CALIBRATE              ; adaptive via KAMP (objects above)
M109 S{temp}
KOMB                            ; wipe the ooze from heating up
G1 Z10 F600                     ; clear earlier test prints (max 6 mm) during the travel
G1 X{purge_x0:.1f} Y{purge_y:.1f} F12000
G1 Z0.5 F600
G1 E1.5 F1800                   ; undo PRINT_END/previous tip retract
G1 X{purge_x0 + purge_len:.1f} E{purge_e:.2f} F1200    ; purge line
G1 X{purge_x0 + purge_len + 5:.1f} F6000     ; wipe (first travel of the test retracts)
G1 Z1 F600
"""


def end_gcode(bed):
    """Keep the bed hot for the next remote test; nozzle off, park at the rear."""
    return f"""G1 E-1.5 F1800
M104 S0
M107
G91
G1 Z10 F600
G90
G1 X175 Y325 F12000
M140 S{bed}                     ; bed stays hot for the next test
SET_IDLE_TIMEOUT TIMEOUT=1800
"""


# ---------------------------------------------------------------------------------------------
# Test zones: each test is one connected piece with raised labels (2026-11-27).
# A one-layer "web" (printed with the test's first layer) joins the test elements and carries
# the labels; the labels are single strokes printed on the web in layers 2 and 3.
# ---------------------------------------------------------------------------------------------
WEB_W = 0.5            # web line width
LABEL_W = 0.45         # label stroke width
LABEL_H = 0.2          # label layer height
LABEL_LAYERS = 2       # raised 0.4 mm
STRIP = 5.5            # standard label strip height (mm) for 3.5 mm text

# Stroke font on a 4 x 6 grid (x right, y up). Each glyph = list of polylines.
_F = {
    "0": [[(0,0),(4,0),(4,6),(0,6),(0,0)],[(0,0),(4,6)]],
    "1": [[(1,5),(2,6),(2,0)],[(1,0),(3,0)]],
    "2": [[(0,6),(4,6),(4,3),(0,3),(0,0),(4,0)]],
    "3": [[(0,6),(4,6),(4,0),(0,0)],[(1,3),(4,3)]],
    "4": [[(0,6),(0,3),(4,3)],[(4,6),(4,0)]],
    "5": [[(4,6),(0,6),(0,3),(4,3),(4,0),(0,0)]],
    "6": [[(4,6),(0,6),(0,0),(4,0),(4,3),(0,3)]],
    "7": [[(0,6),(4,6),(1,0)]],
    "8": [[(0,0),(4,0),(4,6),(0,6),(0,0)],[(0,3),(4,3)]],
    "9": [[(4,3),(0,3),(0,6),(4,6),(4,0),(0,0)]],
    ".": [[(1.6,0),(2.4,0),(2.4,0.8),(1.6,0.8),(1.6,0)]],
    "-": [[(0.5,3),(3.5,3)]],
    ">": [[(0.5,5),(3.5,3),(0.5,1)]],
    "/": [[(0,0),(4,6)]],
    "+": [[(0.5,3),(3.5,3)],[(2,1.5),(2,4.5)]],
    "A": [[(0,0),(0,4),(2,6),(4,4),(4,0)],[(0,3),(4,3)]],
    "B": [[(0,0),(0,6),(3,6),(4,5),(4,4),(3,3),(0,3)],[(3,3),(4,2),(4,1),(3,0),(0,0)]],
    "C": [[(4,6),(0,6),(0,0),(4,0)]],
    "D": [[(0,0),(0,6),(2.5,6),(4,4.5),(4,1.5),(2.5,0),(0,0)]],
    "E": [[(4,6),(0,6),(0,0),(4,0)],[(0,3),(3,3)]],
    "F": [[(4,6),(0,6),(0,0)],[(0,3),(3,3)]],
    "G": [[(4,6),(0,6),(0,0),(4,0),(4,3),(2,3)]],
    "H": [[(0,0),(0,6)],[(4,0),(4,6)],[(0,3),(4,3)]],
    "I": [[(1,6),(3,6)],[(2,6),(2,0)],[(1,0),(3,0)]],
    "J": [[(4,6),(4,0),(0,0),(0,2)]],
    "K": [[(0,0),(0,6)],[(4,6),(0,3),(4,0)]],
    "L": [[(0,6),(0,0),(4,0)]],
    "M": [[(0,0),(0,6),(2,3),(4,6),(4,0)]],
    "N": [[(0,0),(0,6),(4,0),(4,6)]],
    "O": [[(0,0),(4,0),(4,6),(0,6),(0,0)]],
    "P": [[(0,0),(0,6),(4,6),(4,3),(0,3)]],
    "Q": [[(0,0),(4,0),(4,6),(0,6),(0,0)],[(2.5,1.5),(4.5,-0.5)]],
    "R": [[(0,0),(0,6),(4,6),(4,3),(0,3),(4,0)]],
    "S": [[(4,6),(0,6),(0,3),(4,3),(4,0),(0,0)]],
    "T": [[(0,6),(4,6)],[(2,6),(2,0)]],
    "U": [[(0,6),(0,0),(4,0),(4,6)]],
    "V": [[(0,6),(2,0),(4,6)]],
    "W": [[(0,6),(1,0),(2,3),(3,0),(4,6)]],
    "X": [[(0,0),(4,6)],[(0,6),(4,0)]],
    "Y": [[(0,6),(2,3),(4,6)],[(2,3),(2,0)]],
    "Z": [[(0,6),(4,6),(0,0),(4,0)]],
    " ": [],
}
_ADV = 5.6             # glyph advance in grid units (glyph 4 wide + gap)


def text_width(s, h):
    return (len(s) * _ADV - (_ADV - 4)) * h / 6.0 if s else 0.0


def text_strokes(s, x, y, h, align="left"):
    """Polylines (mm) for text s with cap height h; (x, y) = bottom-left (or bottom-centre)."""
    k = h / 6.0
    if align == "center":
        x -= text_width(s, h) / 2
    out = []
    for i, ch in enumerate(s.upper()):
        for pl in _F.get(ch, _F["-"]):
            out.append([(x + (i * _ADV + px) * k, y + py * k) for px, py in pl])
    return out


def _travel(w, x, y, z, hop=0.6, ret=0.5, cur=None):
    if cur and math.hypot(x - cur[0], y - cur[1]) < 2.0:
        w(f"G1 X{x:.3f} Y{y:.3f} F6000")
        return
    w(f"G1 E-{ret} F2400")
    w(f"G1 Z{z + hop:.3f} F1800")
    w(f"G1 X{x:.3f} Y{y:.3f} F18000")
    w(f"G1 Z{z:.3f} F1800")
    w(f"G1 E{ret} F2400")


def web_gcode(rects, obstacles, z, h, speed=30.0, overlap=0.3):
    """One solid layer over `rects` (x0,y0,x1,y1), lines along X, cut around `obstacles`
    (('rect', x0,y0,x1,y1) or ('circle', cx,cy,r)) so it only overlaps them by `overlap`.
    Starts and ends un-retracted at height z (the test's first layer)."""
    out = ["; ---- zone web (joins the test elements, carries the labels)"]
    w = out.append
    emm = e_per_mm(WEB_W, h, 1.0)
    sp = spacing(WEB_W, h)
    cur = None
    for (x0, y0, x1, y1) in rects:
        n = max(1, int((y1 - y0 - WEB_W) / sp) + 1)
        for j in range(n):
            yy = y0 + WEB_W / 2 + j * (y1 - y0 - WEB_W) / max(1, n - 1) if n > 1 else (y0 + y1) / 2
            segs = [(x0 + WEB_W / 2, x1 - WEB_W / 2)]
            for ob in obstacles:
                if ob[0] == "rect":
                    _, a0, b0, a1, b1 = ob
                    if b0 + overlap <= yy <= b1 - overlap:
                        cut = (a0 + overlap, a1 - overlap)
                    else:
                        continue
                else:
                    _, cx, cy, r = ob
                    rr = r - overlap
                    if abs(yy - cy) >= rr:
                        continue
                    dx = math.sqrt(rr * rr - (yy - cy) ** 2)
                    cut = (cx - dx, cx + dx)
                nxt = []
                for s0, s1 in segs:
                    if cut[1] <= s0 or cut[0] >= s1:
                        nxt.append((s0, s1))
                        continue
                    if cut[0] > s0:
                        nxt.append((s0, cut[0]))
                    if cut[1] < s1:
                        nxt.append((cut[1], s1))
                segs = nxt
            segs = [sg for sg in segs if sg[1] - sg[0] >= 1.0]
            if j % 2:
                segs = [(s1, s0) for s0, s1 in reversed(segs)]
            for s0, s1 in segs:
                if cur is None:
                    w(f"G1 Z{z + 0.6:.3f} F1800")
                    w(f"G1 X{s0:.3f} Y{yy:.3f} F18000")
                    w(f"G1 Z{z:.3f} F1800")
                else:
                    _travel(w, s0, yy, z, cur=cur)
                w(f"G1 X{s1:.3f} Y{yy:.3f} E{abs(s1 - s0) * emm:.5f} F{speed * 60:.0f}")
                cur = (s1, yy)
    return "\n".join(out)


def label_gcode(labels, z, speed=20.0):
    """One layer of label strokes at height z. labels: list of (text, x, y, h, align).
    Starts and ends un-retracted at height z (the generator's next travel retracts)."""
    out = [f"; ---- labels z={z:.2f}"]
    w = out.append
    emm = e_per_mm(LABEL_W, LABEL_H, 1.0)
    cur = None
    for text, x, y, h, align in labels:
        for pl in text_strokes(text, x, y, h, align):
            if cur is None:
                w(f"G1 Z{z + 0.6:.3f} F1800")
                w(f"G1 X{pl[0][0]:.3f} Y{pl[0][1]:.3f} F18000")
                w(f"G1 Z{z:.3f} F1800")
            else:
                _travel(w, pl[0][0], pl[0][1], z, cur=cur)
            for (xa, ya), (xb, yb) in zip(pl, pl[1:]):
                w(f"G1 X{xb:.3f} Y{yb:.3f} E{math.hypot(xb - xa, yb - ya) * emm:.5f} F{speed * 60:.0f}")
            cur = pl[-1]
    return "\n".join(out)
