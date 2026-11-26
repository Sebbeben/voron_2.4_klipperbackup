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
LAYOUT_FILE = os.path.expanduser("~/printer_data/config/tools/bed_layout.json")
FIL_AREA = math.pi * (1.75 / 2) ** 2

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


def find_spot(w, h, margin=5.0):
    """First free (x0, y0) for a w x h footprint, scanning front-left to rear-right."""
    used = [tuple(r["rect"]) for r in load_layout()]
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


def record(rect, name):
    lay = load_layout()
    lay.append({"name": name, "rect": [round(v, 1) for v in rect],
                "time": time.strftime("%Y-%m-%d %H:%M")})
    json.dump(lay, open(LAYOUT_FILE, "w"), indent=1)


def start_gcode(bed, temp, purge_x0, purge_y, purge_len=60.0):
    """Home, QGL, Z home, adaptive mesh (KAMP, objects must be defined before), purge.
    Does not use PRINT_START (its fixed prime line would print on top of earlier ones)."""
    return f"""M140 S{bed}
M104 S150                       ; warm, non-oozing nozzle for Tap
SET_IDLE_TIMEOUT TIMEOUT=10800
G90
M83
G28
M190 S{bed}
BED_MESH_CLEAR
QUAD_GANTRY_LEVEL
G28 Z
BED_MESH_CALIBRATE              ; adaptive via KAMP (objects above)
G1 Z5 F600
G1 X{purge_x0:.1f} Y{purge_y:.1f} F12000
M109 S{temp}
G1 Z0.5 F600
G1 E1.5 F1800                   ; undo PRINT_END/previous tip retract
G1 X{purge_x0 + purge_len:.1f} E14 F1200    ; purge line
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
SET_IDLE_TIMEOUT TIMEOUT=10800
"""
