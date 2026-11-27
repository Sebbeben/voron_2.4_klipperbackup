"""Simple SVG sketches for the belt tension panel: where to pluck and where the 150 mm span is.

Voron 2.4 conventions used (seen from the front):
  B belt = left front span, A belt = right front span (front idler -> X/Y-joint idler).
  Z0 front-left, Z1 rear-left, Z2 rear-right, Z3 front-right (stepper_z ... stepper_z3).
Z belts (Voron docs): fixed side of the belt, 150 mm from the Z idler centres.
Sides: Voron config template "X-MOT (B Motor) Left" / "Y-MOT (A Motor) Right"; each motor's belt runs
to the front idler on its own side, so the left front span is B, the right one A.
Mic symbol: where to put a movable microphone (camera mic or belt sensor) - next to the middle of
the span, a few cm away, not touching the belt. Drawn schematic, not to exact scale.
"""

HL = "#ff9800"        # belt being measured
DIM = "#4fc3f7"       # 150 mm dimension
FRAME = "#5f6b73"
BELT = "#8a969e"
TEXT = "#e0e0e0"
GREY = "#9e9e9e"
Z_CORNERS = {"Z0": ("front", "left"), "Z1": ("rear", "left"), "Z2": ("rear", "right"), "Z3": ("front", "right")}


def _svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="sans-serif">{body}</svg>').encode()


def _dim_v(x, y1, y2, label, side=1, dy=0):
    """Vertical dimension line with arrows and a label (dy shifts the label, e.g. away from the pluck arrow)."""
    a = 7
    tx = x + side * 8
    anchor = "start" if side > 0 else "end"
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{DIM}" stroke-width="2"/>'
            f'<path d="M{x - a / 2},{y1 + a} L{x},{y1} L{x + a / 2},{y1 + a}" fill="none" stroke="{DIM}" stroke-width="2"/>'
            f'<path d="M{x - a / 2},{y2 - a} L{x},{y2} L{x + a / 2},{y2 - a}" fill="none" stroke="{DIM}" stroke-width="2"/>'
            f'<text x="{tx}" y="{(y1 + y2) / 2 + 6 + dy}" fill="{DIM}" font-size="17" font-weight="bold" '
            f'text-anchor="{anchor}">{label}</text>')


MIC = "#ce93d8"


def _mic(x, y, side=1, label="mic here"):
    """Microphone symbol (capsule + stand) with a label; side = which way the label goes."""
    anchor = "start" if side > 0 else "end"
    return (f'<rect x="{x - 6}" y="{y - 12}" width="12" height="18" rx="6" fill="none" stroke="{MIC}" stroke-width="2.5"/>'
            f'<path d="M{x - 10},{y} a10,10 0 0,0 20,0" fill="none" stroke="{MIC}" stroke-width="2"/>'
            f'<line x1="{x}" y1="{y + 10}" x2="{x}" y2="{y + 15}" stroke="{MIC}" stroke-width="2"/>'
            f'<text x="{x + side * 14}" y="{y + 2}" fill="{MIC}" font-size="12" text-anchor="{anchor}">{label}</text>')


def _pluck(x, y, side=1):
    """Arrow pointing at the belt + 'pluck'."""
    x0 = x + side * 46
    anchor = "start" if side > 0 else "end"
    return (f'<line x1="{x0}" y1="{y}" x2="{x + side * 9}" y2="{y}" stroke="{HL}" stroke-width="3"/>'
            f'<path d="M{x + side * 17},{y - 6} L{x + side * 8},{y} L{x + side * 17},{y + 6}" fill="none" '
            f'stroke="{HL}" stroke-width="3"/>'
            f'<text x="{x0 + side * 3}" y="{y + 6}" fill="{HL}" font-size="16" font-weight="bold" '
            f'text-anchor="{anchor}">pluck</text>')


def ab_sketch(which, w=260, h=290, mic=True):
    """Top view. which: 'B', 'A' or 'both' (setup view)."""
    L, R, T, F = 54, w - 54, 26, h - 38          # belt x positions, rear, front idlers
    jy = F - 120                                 # X/Y joints at the measuring position (150 mm span)
    b = []
    b.append(f'<rect x="{L - 26}" y="{T - 16}" width="{R - L + 52}" height="{F - T + 30}" fill="none" '
             f'stroke="{FRAME}" stroke-width="3" rx="4"/>')
    # rear motors
    for x, name in ((L, "B"), (R, "A")):
        b.append(f'<rect x="{x - 12}" y="{T - 12}" width="24" height="24" fill="#2b3338" stroke="{FRAME}"/>'
                 f'<text x="{x}" y="{T + 5}" fill="{GREY}" font-size="13" text-anchor="middle">{name}</text>')
    # belts along the sides (grey)
    for x in (L, R):
        b.append(f'<line x1="{x}" y1="{T + 12}" x2="{x}" y2="{F}" stroke="{BELT}" stroke-width="3"/>')
    # gantry with X/Y joints and toolhead
    b.append(f'<line x1="{L}" y1="{jy}" x2="{R}" y2="{jy}" stroke="{FRAME}" stroke-width="9"/>')
    b.append(f'<rect x="{(L + R) / 2 - 20}" y="{jy - 20}" width="40" height="40" rx="5" fill="#3a444a" stroke="{FRAME}"/>')
    for x in (L, R):
        b.append(f'<circle cx="{x}" cy="{jy}" r="9" fill="#2b3338" stroke="{TEXT}" stroke-width="2"/>')
        b.append(f'<circle cx="{x}" cy="{F}" r="9" fill="#2b3338" stroke="{TEXT}" stroke-width="2"/>')
    sides = {"B": [(L, 1)], "A": [(R, -1)], "both": [(L, 1), (R, -1)]}[which]
    for x, s in sides:
        b.append(f'<line x1="{x}" y1="{F - 9}" x2="{x}" y2="{jy + 9}" stroke="{HL}" stroke-width="7"/>')
        both = which == "both"
        b.append(_dim_v(x + s * 22, jy, F, "150" if both else "150 mm", s, 0 if both else 30))
        if not both:
            b.append(_pluck(x, (jy + F) / 2, s))           # pluck in the middle of the span
            if mic:   # movable mic: at mid-span, between the belt and the frame
                b.append(_mic(x - s * 13, (jy + F) / 2, -s, "mic"))
    b.append(f'<text x="{w / 2}" y="{h - 6}" fill="{GREY}" font-size="14" text-anchor="middle">FRONT</text>')
    b.append(f'<text x="{L}" y="{F + 26}" fill="{GREY}" font-size="11" text-anchor="middle">idler</text>'
             f'<text x="{R}" y="{F + 26}" fill="{GREY}" font-size="11" text-anchor="middle">idler</text>')
    b.append(f'<text x="{(L + R) / 2}" y="{jy - 28}" fill="{GREY}" font-size="11" text-anchor="middle">'
             f'X/Y joints</text>')
    return _svg(w, h, "".join(b))


def z_sketch(slot, w=260, h=290, mic=True):
    """Side view of one Z drive + mini top view with the corner. slot: 'Z0'..'Z3' or None (setup)."""
    b = []
    bx, iy = 104, h - 46                # strand x (fixed side), Z idler centre y
    gy = iy - 150                       # gantry clamp at 150 mm (schematic)
    # Z drive unit
    b.append(f'<rect x="{bx - 30}" y="{iy - 16}" width="92" height="40" rx="4" fill="#2b3338" stroke="{FRAME}"/>')
    b.append(f'<text x="{bx + 16}" y="{iy + 38}" fill="{GREY}" font-size="11" text-anchor="middle">Z drive / idler</text>')
    b.append(f'<circle cx="{bx}" cy="{iy}" r="9" fill="#2b3338" stroke="{TEXT}" stroke-width="2"/>')
    b.append(f'<circle cx="{bx + 32}" cy="{iy}" r="9" fill="#2b3338" stroke="{TEXT}" stroke-width="2"/>')
    # gantry clamp
    b.append(f'<rect x="{bx - 24}" y="{gy - 26}" width="80" height="22" rx="3" fill="#3a444a" stroke="{FRAME}"/>')
    b.append(f'<text x="{bx + 16}" y="{gy - 32}" fill="{GREY}" font-size="11" text-anchor="middle">gantry</text>')
    # strands: fixed side highlighted, other side grey
    b.append(f'<line x1="{bx + 32}" y1="{iy - 9}" x2="{bx + 32}" y2="{gy - 4}" stroke="{BELT}" stroke-width="3"/>')
    b.append(f'<line x1="{bx}" y1="{iy - 9}" x2="{bx}" y2="{gy - 4}" stroke="{HL}" stroke-width="7"/>')
    b.append(_dim_v(bx + 54, gy, iy, "150", 1, 0))
    b.append(f'<text x="{bx + 62}" y="{(gy + iy) / 2 + 24}" fill="{DIM}" font-size="13" text-anchor="start">mm</text>')
    b.append(f'<text x="{bx - 6}" y="{gy + 18}" fill="{HL}" font-size="11" text-anchor="end">fixed</text>')
    b.append(_pluck(bx, (gy + iy) / 2, -1) if slot else "")     # middle of the span, from the left
    if slot and mic:   # between the strands, at mid-span; label below
        b.append(_mic(bx + 16, (gy + iy) / 2, 1, ""))
        b.append(f'<text x="{bx + 16}" y="{(gy + iy) / 2 + 30}" fill="{MIC}" font-size="12" '
                 f'text-anchor="middle">mic</text>')
    # mini top view with the four Z corners
    mx, my, ms = w - 74, 20, 44
    b.append(f'<rect x="{mx}" y="{my}" width="{ms}" height="{ms}" fill="none" stroke="{FRAME}" stroke-width="2"/>')
    b.append(f'<text x="{mx + ms / 2}" y="{my + ms + 22}" fill="{GREY}" font-size="11" text-anchor="middle">front</text>')
    for name, (fr, side) in Z_CORNERS.items():
        cx = mx + (0 if side == "left" else ms)
        cy = my + (ms if fr == "front" else 0)
        on = name == slot
        b.append(f'<circle cx="{cx}" cy="{cy}" r="{9 if on else 6}" fill="{HL if on else "#2b3338"}" '
                 f'stroke="{HL if on else GREY}" stroke-width="2"/>')
        tx = cx + (-13 if side == "left" else 13)      # labels outside the square
        b.append(f'<text x="{tx}" y="{cy + 4}" fill="{HL if on else GREY}" font-size="12" '
                 f'font-weight="{"bold" if on else "normal"}" text-anchor="{"end" if side == "left" else "start"}">'
                 f'{name}</text>')
    return _svg(w, h, "".join(b))


def sketch(slot, w=260, h=290, mic=True):
    if slot in ("A", "B", "both"):
        return ab_sketch(slot, w, h, mic)
    return z_sketch(slot, w, h, mic)


if __name__ == "__main__":       # write preview SVGs: python3 ks_belt_sketch.py OUTDIR
    import os, sys
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for s in ("B", "A", "both", "Z0", "Z2", None):
        with open(os.path.join(out, f"sketch_{s}.svg"), "wb") as f:
            f.write(sketch(s))
