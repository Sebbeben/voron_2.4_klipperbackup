#!/usr/bin/env python3
"""Generate KiCad 8 PCB files with all footprints PLACED (not routed) for both boards.

    python3 gen_schematic.py && python3 gen_pcb.py

- Footprints, values and nets come from the generated schematics (netcheck.py extracts the nets).
- Each footprint carries the symbol UUID path, so KiCad's "Update PCB from Schematic" (F8)
  matches them instead of adding duplicates.
- Placement is the PLACE table below (courtyard centre, rotation). The script refuses to write
  a board with overlapping courtyards or parts outside the outline.
- Routing, copper pours and silkscreen tidy-up are done by hand in KiCad. Once you start
  moving parts in KiCad, stop re-running this script (it overwrites the .kicad_pcb).
KiCad 8.0.8 library footprints are read from ~/kicad_libsrc_8.0.8/footprints (not in git).
"""
import math, os, re, sys, uuid
sys.dont_write_bytecode = True
import kilib, netcheck
from gen_schematic import sym_uuid

HERE = os.path.dirname(os.path.abspath(__file__))
FPLIB = os.environ.get("KICAD_FPSRC", os.path.expanduser("~/kicad_libsrc_8.0.8/footprints"))
ORIGIN = (100.0, 50.0)          # board top-left corner on the PCB page
SOLDER_CLEAR = 1.0                 # mm free around back-side THT pads for hand soldering
MODEL_VAR = "KICAD10_3DMODEL_DIR"   # KiCad 10 library 3D models (STEP); custom ones use ${KIPRJMOD}

def U():
    return str(uuid.uuid4())

# --------------------------------------------------------------------------
# Footprint handling
# --------------------------------------------------------------------------
def fp_text(lib_fp):
    lib, name = lib_fp.split(":")
    if lib == "PowerMonitor":
        path = os.path.join(HERE, "PowerMonitor.pretty", name + ".kicad_mod")
    else:
        path = os.path.join(FPLIB, lib + ".pretty", name + ".kicad_mod")
    return open(path).read()

def children(block):
    """Top-level child blocks of an s-expression block."""
    out, i, depth = [], 1, 0
    while True:
        j = block.find("(", i)
        if j < 0:
            break
        c = kilib._block(block, j)
        out.append(c)
        i = j + len(c)
    return out

def courtyard(text):
    xs, ys = [], []
    for c in children(text):
        if not c.startswith("(fp_") or '(layer "F.CrtYd")' not in c:
            continue
        pts = [tuple(map(float, p)) for p in re.findall(r'\((?:start|end|xy|mid|center) ([-\d.]+) ([-\d.]+)\)', c)]
        if c.startswith("(fp_circle"):
            (cx, cy), (ex, ey) = pts[0], pts[1]
            r = math.hypot(ex - cx, ey - cy)
            pts = [(cx - r, cy - r), (cx + r, cy + r)]
        for x, y in pts:
            xs.append(x); ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)

def tht_pads(text):
    """[(x, y, half_size)] of through-hole pads in local coordinates."""
    out = []
    for c in children(text):
        if c.startswith("(pad ") and (" thru_hole " in c or " np_thru_hole " in c):
            m = re.search(r'\(at ([-\d.]+) ([-\d.]+)', c); s = re.search(r'\(size ([-\d.]+) ([-\d.]+)\)', c)
            out.append((float(m.group(1)), float(m.group(2)), max(float(s.group(1)), float(s.group(2))) / 2))
    return out

def rot(x, y, a):
    """KiCad PCB rotation (counter-clockwise on screen, y down)."""
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return x * c + y * s, -x * s + y * c

def flip_text(t):
    """Mirror a footprint to the back side (KiCad top/bottom flip in local coordinates):
    y -> -y, local angles negated, F.* layers -> B.*, texts mirrored."""
    t = re.sub(r'\((at|start|end|center|mid|xy) ([-\d.]+) ([-\d.]+)',
               lambda m: "(%s %s %s" % (m.group(1), m.group(2), repr(-float(m.group(3)) + 0.0).rstrip("0").rstrip(".") if float(m.group(3)) else "0"), t)
    t = re.sub(r'"F\.(SilkS|Fab|CrtYd|Paste|Mask|Cu|Adhes)"', r'"B.\1"', t)
    t = t.replace("(justify left)", "(justify left mirror)").replace("(justify right)", "(justify right mirror)")
    t = re.sub(r'\(effects \(font ([^)]*\)[^)]*)\)\)', lambda m: m.group(0) if "mirror" in m.group(0) else m.group(0)[:-1] + " (justify mirror))", t)
    return t

def fp_block(lib_fp, ref, value, x, y, a, padnets, path, sheetfile, lcsc, side="F"):
    t = fp_text(lib_fp)
    if side == "B":
        t = flip_text(t)
    name = lib_fp.split(":")[1]
    parts = [c for c in children(t) if not re.match(r'\((version|generator|generator_version|layer) ', c)]
    out = []
    for c in parts:
        if c.startswith("(property "):
            key = re.match(r'\(property "([^"]+)"', c).group(1)
            if key == "Reference":
                c = re.sub(r'\(property "Reference" "[^"]*"', '(property "Reference" "%s"' % ref, c, 1)
            elif key == "Value":
                c = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "%s"' % value.replace('"', "'"), c, 1)
            elif key == "Footprint":
                c = re.sub(r'\(property "Footprint" "[^"]*"', '(property "Footprint" "%s"' % lib_fp, c, 1)
        if c.startswith("(property ") or c.startswith("(fp_text ") or c.startswith("(pad "):
            def fix_at(m):
                ang = (-float(m.group(3) or 0) if side == "B" else float(m.group(3) or 0)) + a
                ang = ang % 360
                return "(at %s %s%s)" % (m.group(1), m.group(2), (" %g" % ang) if ang else "")
            c = re.sub(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', fix_at, c, 1)
        if c.startswith("(pad "):
            num = re.match(r'\(pad "([^"]*)"', c).group(1)
            if num in padnets:
                n, nn = padnets[num]
                c = c[:-1] + ' (net %d "%s"))' % (n, nn)
        if c.startswith("(model "):
            c = re.sub(r'\$\{KICAD\d+_3DMODEL_DIR\}([^"]*)\.wrl', r'${%s}\1.step' % MODEL_VAR, c)
        if "(uuid " in c:
            c = re.sub(r'\(uuid "[^"]*"\)', '(uuid "%s")' % U(), c)
        out.append(c)
    head = ('(footprint "%s" (layer "%s") (uuid "%s") (at %.3f %.3f%s)'
            % (lib_fp, "B.Cu" if side == "B" else "F.Cu", U(), x, y, (" %g" % a) if a else ""))
    extra = ['(property "LCSC" "%s" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "%s") (effects (font (size 1 1) (thickness 0.15))))'
             % (lcsc, U())] if lcsc else []
    extra += ['(path "/%s")' % path, '(sheetname "Root")', '(sheetfile "%s")' % sheetfile]
    return head + "\n" + "\n".join(out[:1] + extra + out[1:]) + ")"

# --------------------------------------------------------------------------
# Schematic -> parts + nets
# --------------------------------------------------------------------------
def read_schematic(sch):
    t = open(os.path.join(HERE, sch)).read()
    ls = t.index("(lib_symbols"); lb = kilib._block(t, ls)
    body = t[:ls] + t[ls + len(lb):]
    parts = {}
    for m in re.finditer(r'\(symbol \(lib_id "([^"]+)"\)', body):
        blk = kilib._block(body, m.start())
        prop = lambda k: (re.search(r'\(property "%s" "([^"]*)"' % k, blk) or [None, ""])[1]
        ref = prop("Reference")
        if ref.startswith("#") or not prop("Footprint"):
            continue
        parts[ref] = dict(fp=prop("Footprint"), value=prop("Value"), lcsc=prop("LCSC"), dnp="(dnp yes)" in blk)
    nets, _ = netcheck.netlist(os.path.join(HERE, sch))
    padnet, names = {}, []
    for name, members in nets:
        if len(members) < 2 and name == "?":
            continue                       # no-connect pin
        if name == "?":
            r, p = members[0].split(".")
            name = "Net-(%s-Pad%s)" % (r, p)
        names.append(name)
        for mbr in members:
            r, p = mbr.split(".")
            padnet.setdefault(r, {})[p] = name
    return parts, padnet, sorted(set(names))

# --------------------------------------------------------------------------
# Board writer
# --------------------------------------------------------------------------
LAYERS = '''(layers (0 "F.Cu" signal) (31 "B.Cu" signal) (32 "B.Adhes" user "B.Adhesive") (33 "F.Adhes" user "F.Adhesive")
(34 "B.Paste" user) (35 "F.Paste" user) (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen")
(38 "B.Mask" user) (39 "F.Mask" user) (40 "Dwgs.User" user "User.Drawings") (41 "Cmts.User" user "User.Comments")
(42 "Eco1.User" user "User.Eco1") (43 "Eco2.User" user "User.Eco2") (44 "Edge.Cuts" user) (45 "Margin" user)
(46 "B.CrtYd" user "B.Courtyard") (47 "F.CrtYd" user "F.Courtyard") (48 "B.Fab" user) (49 "F.Fab" user))'''

def build(board, sch, size, place, texts=(), copper_oz=2):
    parts, padnet, netnames = read_schematic(sch)
    missing = sorted(set(parts) - set(place))
    extra = sorted(set(place) - set(parts))
    assert not missing, "not placed: %s" % missing
    assert not extra, "placed but not in schematic: %s" % extra
    W, H = size
    netid = {n: i + 1 for i, n in enumerate(netnames)}
    boxes, fps, side_of, padboxes = {}, [], {}, []
    for ref, pl in place.items():
        cx, cy, a = pl[:3]
        side = pl[3] if len(pl) > 3 else "F"
        side_of[ref] = side
        p = parts[ref]
        t = fp_text(p["fp"])
        if side == "B":
            t = flip_text(t)
        x1, y1, x2, y2 = courtyard(t)
        lcx, lcy = (x1 + x2) / 2, (y1 + y2) / 2
        rx, ry = rot(lcx, lcy, a)
        ox, oy = ORIGIN[0] + cx - rx, ORIGIN[1] + cy - ry       # footprint origin
        corners = [rot(x, y, a) for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]
        bx = [ox + c[0] for c in corners]; by = [oy + c[1] for c in corners]
        boxes[ref] = (min(bx), min(by), max(bx), max(by))
        pn = {pad: (netid[n], n) for pad, n in padnet.get(ref, {}).items()}
        fps.append(fp_block(p["fp"], ref, p["value"], ox, oy, a, pn,
                            sym_uuid(board, ref), sch, p["lcsc"], side))
        for px, py, hs in tht_pads(t):
            qx, qy = rot(px, py, a)
            padboxes.append((ref, ox + qx, oy + qy, hs + SOLDER_CLEAR))
    # checks: courtyard overlap + inside the board
    errs = []
    refs = sorted(boxes)
    for i, r1 in enumerate(refs):
        a1 = boxes[r1]
        if a1[0] < ORIGIN[0] - 0.01 or a1[1] < ORIGIN[1] - 0.01 or a1[2] > ORIGIN[0] + W + 0.01 or a1[3] > ORIGIN[1] + H + 0.01:
            if not parts[r1]["fp"].startswith(("TerminalBlock", "Connector_BarrelJack", "PowerMonitor:RJ45")):
                errs.append("outside board: %s %s" % (r1, tuple(round(v - o, 1) for v, o in zip(a1, ORIGIN * 2))))
        for r2 in refs[i + 1:]:
            a2 = boxes[r2]
            both = "MountingHole" in parts[r1]["fp"] or "MountingHole" in parts[r2]["fp"]
            if side_of[r1] != side_of[r2] and not both:
                continue                   # parts on opposite sides may overlap
            if a1[0] < a2[2] - 0.01 and a2[0] < a1[2] - 0.01 and a1[1] < a2[3] - 0.01 and a2[1] < a1[3] - 0.01:
                errs.append("courtyard overlap: %s / %s" % (r1, r2))
    # THT pads go through the board: no part on either side may sit on them (+ soldering access)
    for pref, px, py, hs in padboxes:
        for r, b in boxes.items():
            if r == pref or "MountingHole" in parts[r]["fp"]:
                continue
            if b[0] < px + hs and px - hs < b[2] and b[1] < py + hs and py - hs < b[3]:
                errs.append("on a THT pad of %s: %s" % (pref, r))
    out = ['(kicad_pcb (version 20240108) (generator "gen_pcb.py") (generator_version "8.0")',
           '(general (thickness 1.6) (legacy_teardrops no))', '(paper "A3")', LAYERS,
           '(setup (pad_to_mask_clearance 0) (allow_soldermask_bridges_in_footprints no))',
           '(net 0 "")'] + ['(net %d "%s")' % (i, n) for n, i in netid.items()]
    out += fps
    x0, y0 = ORIGIN
    out.append('(gr_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts") (uuid "%s"))'
               % (x0, y0, x0 + W, y0 + H, U()))
    for s, x, y, size_ in texts:
        out.append('(gr_text "%s" (at %.3f %.3f 0) (layer "F.SilkS") (uuid "%s") (effects (font (size %g %g) (thickness 0.15)) (justify left)))'
                   % (s, x0 + x, y0 + y, U(), size_, size_))
    out.append(")")
    txt = "\n".join(out)
    assert txt.count("(") == txt.count(")"), "unbalanced"
    path = os.path.join(HERE, board + ".kicad_pcb")
    open(path, "w").write(txt + "\n")
    print("wrote %s: %d footprints, %d nets, %.0f x %.0f mm" % (os.path.basename(path), len(fps), len(netid), W, H))
    for e in errs:
        print("  CHECK:", e)
    return errs, boxes

# --------------------------------------------------------------------------
# Main board placement: (courtyard centre x, y in mm from the board top-left corner, rotation)
# --------------------------------------------------------------------------
# 100 x 100 mm (JLC price step). Power flows down: J1 (left edge) -> RS1 -> 24V_BUS band
# (F.Cu pour, y ~60-66) -> one column per output: shunt, fuse (2 clips, vertical), terminal on the
# bottom edge. 5 V: J2 (right edge) -> RS8 -> 5V_BUS band (right end) -> column 7 (Pi).
# INA3221 + filter row above the band (Kelvin pairs on B.Cu under the pour).
# Top edge: relay coil, Pi header, alert out, AC jack, RJ45. MCU + mains analog in the middle,
# away from the high-current copper. See the memory note / BOM.md for the spacing rules.
MAIN_W, MAIN_H = 100.0, 100.0
PITCH = 12.8
COL = [11.55 + PITCH * k for k in range(7)]      # output columns F1..F7 (terminal courtyard centres)
def main_place():
    P = {}
    shunts = ["RS2", "RS3", "RS4", "RS5", "RS6", "RS7", "RS9"]
    for k, x in enumerate(COL):
        n = k + 1
        P["J%d" % (n + 2)] = (x, MAIN_H - 5.4, 0)          # wire entry down, on the bottom edge
        P["F%dB" % n] = (x, 86.3, 270)                      # load-side clip
        P["F%dA" % n] = (x, 86.3 - 9.73, 270)               # supply-side clip (ATM fuse = 9.73 mm)
        P[shunts[k]] = (x, 69.8, 270)                       # pin 1 (bus side) on top
        P["RL%d" % n] = (x + PITCH / 2, 76.5, 90)           # in the gap between columns
        P["LEDF%d" % n] = (x + PITCH / 2, 84.5, 270)
    # 24 V input, left edge (wire entry left)
    P["J1"] = (5.4, 54.0, 270)
    P["RS1"] = (14.5, 54.5, 270)                         # 24V_IN top -> 24V_BUS bottom (band)
    P["D1"] = (19.5, 51.0, 90)
    P["C14"] = (24.5, 56.5, 90)
    P["C15"] = (29.0, 56.5, 90)
    P["TP1"] = (13.0, 48.0, 0)
    P["TP2"] = (33.0, 58.0, 0)
    # 5 V input, right edge
    P["J2"] = (MAIN_W - 5.4, 54.0, 90)
    P["RS8"] = (86.0, 54.5, 270)                         # 5V_IN top -> 5V_BUS bottom
    P["D2"] = (80.5, 51.0, 90)
    P["C16"] = (76.0, 56.5, 90)
    P["TP3"] = (71.5, 58.0, 0)
    # INA row + filter triplets (R IN+ side, C, R IN- side per channel)
    for i, (u, x) in enumerate((("U1", 24.0), ("U2", 50.0), ("U3", 76.0))):
        P[u] = (x, 37.0, 0)
        P["C%d" % (10 + i)] = (x + 5.0, 34.5, 90)
    for ch in range(1, 10):
        x = 16.0 + (ch - 1) * 8.0
        P["R%d" % (2 * ch - 1)] = (x - 2.2, 45.0, 90)
        P["C%d" % ch] = (x, 45.0, 90)
        P["R%d" % (2 * ch)] = (x + 2.2, 45.0, 90)
    # top edge connectors
    P["J12"] = (13.5, 5.4, 180)                          # relay coil, wire entry up
    P["J10"] = (30.5, 3.5, 0)                            # Pi header
    P["J11"] = (46.0, 3.5, 0)                            # alert out to the Spider
    P["J21"] = (61.0, 8.0, 270)                          # AC jack, opening up
    P["J20"] = (82.0, 9.5, 180)                          # RJ45, opening up
    # relay driver under its terminal
    P["F8"] = (3.0, 16.5, 90)
    P["D15"] = (7.5, 16.5, 90)
    P["R87"] = (11.5, 15.0, 90)
    P["LED11"] = (11.5, 20.0, 90)
    P["Q1"] = (16.5, 15.0, 0)
    P["Q2"] = (16.5, 21.0, 0)
    P["R83"] = (21.5, 13.5, 0)
    P["R84"] = (21.5, 16.0, 0)
    P["R85"] = (21.5, 19.5, 0)
    P["R86"] = (21.5, 22.0, 0)
    # Pi pull-ups + test points under the Pi header
    for i, r in enumerate(["R19", "R20", "R21", "R22"]):
        P[r] = (26.0 + i * 2.5, 10.5, 90)
    for i, r in enumerate(["TP7", "TP8", "TP9", "TP10"]):
        P[r] = (38.0 + i * 3.0, 10.0, 0)
    # MCU block (middle)
    P["U10"] = (44.0, 23.0, 0)
    P["C40"] = (36.5, 14.5, 90)
    P["C41"] = (38.5, 14.5, 90)
    P["C42"] = (40.5, 14.5, 90)
    P["C43"] = (36.5, 23.0, 90)
    P["SW1"] = (31.0, 22.5, 90)
    P["J22"] = (39.5, 32.0, 90)                          # SWD header (inside, not on the edge)
    P["R64"] = (49.5, 31.5, 0)
    P["JP1"] = (53.5, 31.5, 0)
    P["R65"] = (51.0, 17.0, 90)
    P["LED10"] = (53.0, 17.0, 90)
    for i, r in enumerate(["R60", "R61", "R62"]):
        P[r] = (51.0 + i * 2.0, 23.5, 90)
    P["FB1"] = (34.5, 28.5, 0)
    P["TP4"] = (28.0, 30.5, 0)
    P["TP5"] = (31.0, 30.5, 0)
    # 3V3 LDO next to the 5 V input
    P["U12"] = (89.0, 41.0, 0)
    P["C17"] = (85.0, 41.0, 90)
    P["C13"] = (93.0, 41.0, 90)
    # mains analog between the AC jack / RJ45 and the MCU
    P["R72"] = (56.5, 20.0, 90)
    P["R73"] = (58.5, 20.0, 90)
    P["R70"] = (92.5, 21.5, 90)
    P["R71"] = (94.5, 21.5, 90)
    P["C30"] = (96.5, 21.5, 90)
    P["C31"] = (92.5, 26.0, 90)
    P["TP6"] = (95.5, 26.5, 0)
    for i in range(5):                 # channel i: series R, cap, clamp, pull-down (CT only)
        x = 63.0 + i * 5.6
        P["R%d" % (74 + i)] = (x - 1.0, 22.5, 90)
        P["C%d" % (35 + i)] = (x + 1.0, 22.5, 90)
        P["D%d" % (10 + i)] = (x, 27.5, 0)
        if i < 4:
            P["R%d" % (79 + i)] = (x, 31.5, 90)
    # mounting holes: top corners and above the bus band ends
    for r, (x, y) in {"H1": (3.5, 3.5), "H2": (MAIN_W - 3.5, 3.5),
                      "H3": (3.5, 64.0), "H4": (MAIN_W - 3.5, 64.0)}.items():
        P[r] = (x, y, 0)
    return P

# --------------------------------------------------------------------------
# CT board placement
# --------------------------------------------------------------------------
CT_W, CT_H = 100.0, 30.0
def ct_place():
    """One row of CTs: each mains wire passes through its CT along Y (10 mm above the board) and
    must not run over another tall part, so the RJ45 sits to the right of the row."""
    P = {}
    for i in range(4):
        x = 11.6 + i * 19.7
        P["T%d" % (i + 1)] = (x, 7.0, 0)           # all CTs the same direction (P1* side = supply side)
        P["R%d" % (i + 1)] = (x - 4.0, 17.5, 0)
        P["D%d" % (i + 1)] = (x + 4.5, 17.5, 0)
    P["J1"] = (90.4, 12.0, 90)                      # RJ45 opening to the right edge
    for r, (x, y) in {"H1": (3.5, 26.5), "H2": (41.5, 26.5), "H3": (77.0, 26.5), "H4": (96.5, 26.5)}.items():
        P[r] = (x, y, 0)
    return P

if __name__ == "__main__":
    e1, _ = build("main_board", "main_board.kicad_sch", (MAIN_W, MAIN_H), main_place(),
                  texts=[("POWER MONITOR rev 0 - 24.0 V MAX", 30.0, 52.5, 1.2)])
    e2, _ = build("ct_board", "ct_board.kicad_sch", (CT_W, CT_H), ct_place(),
                  texts=[("NO MAINS COPPER - single L wire through each CT", 9.0, 23.0, 1.0)])
    sys.exit(1 if e1 or e2 else 0)
