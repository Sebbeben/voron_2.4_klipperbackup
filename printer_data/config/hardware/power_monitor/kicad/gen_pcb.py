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

def rot(x, y, a):
    """KiCad PCB rotation (counter-clockwise on screen, y down)."""
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return x * c + y * s, -x * s + y * c

def fp_block(lib_fp, ref, value, x, y, a, padnets, path, sheetfile, lcsc):
    t = fp_text(lib_fp)
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
                ang = float(m.group(3) or 0) + a
                ang = ang % 360
                return "(at %s %s%s)" % (m.group(1), m.group(2), (" %g" % ang) if ang else "")
            c = re.sub(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', fix_at, c, 1)
        if c.startswith("(pad "):
            num = re.match(r'\(pad "([^"]*)"', c).group(1)
            if num in padnets:
                n, nn = padnets[num]
                c = c[:-1] + ' (net %d "%s"))' % (n, nn)
        if "(uuid " in c:
            c = re.sub(r'\(uuid "[^"]*"\)', '(uuid "%s")' % U(), c)
        out.append(c)
    head = ('(footprint "%s" (layer "F.Cu") (uuid "%s") (at %.3f %.3f%s)'
            % (lib_fp, U(), x, y, (" %g" % a) if a else ""))
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
    boxes, fps = {}, []
    for ref, (cx, cy, a) in place.items():
        p = parts[ref]
        t = fp_text(p["fp"])
        x1, y1, x2, y2 = courtyard(t)
        lcx, lcy = (x1 + x2) / 2, (y1 + y2) / 2
        rx, ry = rot(lcx, lcy, a)
        ox, oy = ORIGIN[0] + cx - rx, ORIGIN[1] + cy - ry       # footprint origin
        corners = [rot(x, y, a) for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]
        bx = [ox + c[0] for c in corners]; by = [oy + c[1] for c in corners]
        boxes[ref] = (min(bx), min(by), max(bx), max(by))
        pn = {pad: (netid[n], n) for pad, n in padnet.get(ref, {}).items()}
        fps.append(fp_block(p["fp"], ref, p["value"], ox, oy, a, pn,
                            sym_uuid(board, ref), sch, p["lcsc"]))
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
            if a1[0] < a2[2] - 0.01 and a2[0] < a1[2] - 0.01 and a1[1] < a2[3] - 0.01 and a2[1] < a1[3] - 0.01:
                errs.append("courtyard overlap: %s / %s" % (r1, r2))
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
# Power flows top-left -> down: J1 -> RS1 -> 24V_BUS band (F.Cu pour, y ~52-60) -> one shunt per
# output column -> fuse (2 clips) -> output terminal on the bottom edge. INA3221s sit above the
# bus band, Kelvin pairs run on B.Cu under it. Mains analog + MCU top right, away from the
# high-current copper; connectors on the edges with the wire entry facing out.
MAIN_W, MAIN_H = 160.0, 112.0
COL = [30.0 + 18.0 * k for k in range(7)]        # output columns F1..F7
def main_place():
    P = {}
    # outputs: column k -> shunt, fuse clips, LED/R, terminal (wire entry down)
    shunts = ["RS2", "RS3", "RS4", "RS5", "RS6", "RS7", "RS9"]
    for k, x in enumerate(COL):
        n = k + 1
        P["J%d" % (n + 2)] = (x, MAIN_H - 6.0, 0)
        P["F%dA" % n] = (x - 4.865, MAIN_H - 24.0, 0)
        P["F%dB" % n] = (x + 4.865, MAIN_H - 24.0, 0)
        P["RL%d" % n] = (x - 3.0, MAIN_H - 33.0, 0)
        P["LEDF%d" % n] = (x + 3.0, MAIN_H - 33.0, 180)
        P[shunts[k]] = (x, MAIN_H - 44.0, 270)            # pin 1 (bus side) on top
    # 24 V input on the left edge (wire entry left), input shunt into the bus band
    P["J1"] = (5.5, 58.0, 270)
    P["D1"] = (12.0, 48.0, 90)
    P["RS1"] = (18.0, 56.0, 0)
    P["C14"] = (28.0, 52.0, 0)
    P["C15"] = (28.0, 61.0, 0)
    # 5 V input on the right edge, RS8 -> 5V_BUS -> RS9 (column 7) and the LDO
    P["J2"] = (MAIN_W - 5.5, 58.0, 90)
    P["D2"] = (MAIN_W - 12.0, 48.0, 270)
    P["RS8"] = (MAIN_W - 18.0, 56.0, 180)
    P["C16"] = (MAIN_W - 18.0, 62.0, 0)
    # INA3221s above the bus band, filter R/C triplets under each, decoupling next to VS
    inas = {"U1": 40.0, "U2": 84.0, "U3": 129.0}
    for i, (u, x) in enumerate(inas.items()):
        P[u] = (x, 39.0, 0)
        P["C%d" % (10 + i)] = (x + 5.0, 36.0, 90)
    trip_x = {1: 16.0, 2: COL[0], 3: COL[1], 4: COL[2], 5: COL[3], 6: COL[4], 7: COL[5], 8: MAIN_W - 20.0, 9: COL[6]}
    for ch, x in trip_x.items():       # channel ch: R(2ch-1) = IN+ side, C(ch), R(2ch) = IN- side
        y = 47.0
        P["R%d" % (2 * ch - 1)] = (x - 2.2, y, 90)
        P["C%d" % ch] = (x, y, 90)
        P["R%d" % (2 * ch)] = (x + 2.2, y, 90)
    # heater relay driver, top left (coil terminal on the top edge, wire entry up)
    P["J12"] = (16.0, 6.0, 180)
    P["F8"] = (8.0, 17.0, 90)
    P["D15"] = (16.0, 17.0, 90)
    P["R87"] = (23.0, 15.0, 90)
    P["LED11"] = (23.0, 20.0, 90)
    P["Q1"] = (30.0, 15.0, 0)
    P["Q2"] = (30.0, 22.0, 0)
    P["R83"] = (36.0, 14.0, 0)
    P["R84"] = (36.0, 16.5, 0)
    P["R85"] = (36.0, 21.0, 0)
    P["R86"] = (36.0, 23.5, 0)
    # Pi header + alert output on the top edge, pull-ups under them
    P["J10"] = (56.0, 4.5, 0)
    P["J11"] = (71.0, 4.5, 0)
    for i, r in enumerate(["R19", "R20", "R21", "R22"]):
        P[r] = (50.0 + i * 4.0, 13.0, 90)
    # MCU block
    P["U10"] = (98.0, 18.0, 0)
    P["C40"] = (90.0, 11.0, 90)
    P["C41"] = (93.0, 11.0, 90)
    P["C42"] = (96.0, 11.0, 90)
    P["FB1"] = (90.0, 24.5, 90)
    P["SW1"] = (80.0, 25.0, 0)
    P["C43"] = (86.0, 18.0, 90)
    P["J22"] = (84.0, 4.0, 90)
    P["R64"] = (92.0, 4.5, 0)
    P["JP1"] = (97.0, 4.5, 0)
    P["R65"] = (103.0, 4.5, 0)
    P["LED10"] = (108.0, 4.5, 180)
    for i, r in enumerate(["R60", "R61", "R62"]):
        P[r] = (105.0 + i * 3.0, 11.0, 90)
    # 3V3 LDO near the 5 V input
    P["U12"] = (MAIN_W - 12.0, 36.0, 0)
    P["C17"] = (MAIN_W - 18.0, 36.0, 90)
    P["C13"] = (MAIN_W - 6.0, 36.0, 90)
    # mains analog: RJ45 + AC jack on the top edge, RC + clamps between them and the MCU
    P["J20"] = (141.0, 9.5, 180)
    P["J21"] = (121.0, 8.0, 270)
    P["R72"] = (112.0, 13.0, 90)
    P["R73"] = (115.0, 13.0, 90)
    P["R70"] = (130.0, 21.0, 90)
    P["R71"] = (133.0, 21.0, 90)
    P["C30"] = (136.5, 21.0, 90)
    P["C31"] = (140.0, 21.0, 90)
    for i in range(5):                 # channel i: pull-down (CT only), series R, cap, clamp
        x = 108.0 + i * 5.0
        if i < 4:
            P["R%d" % (79 + i)] = (x + 36.0, 26.0, 90)
        P["R%d" % (74 + i)] = (x, 22.0, 90)
        P["C%d" % (35 + i)] = (x, 27.0, 90)
        P["D%d" % (10 + i)] = (x + 1.0, 32.0, 0)
    # test points and mounting holes
    tps = {"TP1": (12.0, 66.0), "TP2": (36.0, 56.0), "TP3": (MAIN_W - 26.0, 62.0), "TP4": (62.0, 22.0),
           "TP5": (92.0, 30.0), "TP6": (143.0, 21.0), "TP7": (64.0, 13.0), "TP8": (67.5, 13.0),
           "TP9": (71.0, 13.0), "TP10": (74.5, 13.0)}
    for r, (x, y) in tps.items():
        P[r] = (x, y, 0)
    for r, (x, y) in {"H1": (4.0, 4.0), "H2": (MAIN_W - 4.0, MAIN_H - 4.0),
                      "H3": (4.0, MAIN_H - 4.0), "H4": (MAIN_W - 4.0, 28.0)}.items():
        P[r] = (x, y, 0)
    return P

# --------------------------------------------------------------------------
# CT board placement
# --------------------------------------------------------------------------
CT_W, CT_H = 112.0, 34.0
def ct_place():
    P = {}
    for i in range(4):
        x = 12.0 + i * 24.0
        P["T%d" % (i + 1)] = (x, 11.0, 0)          # all CTs the same direction (P1* side = supply side)
        P["R%d" % (i + 1)] = (x - 3.0, 24.0, 0)
        P["D%d" % (i + 1)] = (x + 5.0, 24.0, 0)
    P["J1"] = (CT_W - 9.5, 17.0, 90)                # RJ45 opening to the right edge
    for r, (x, y) in {"H1": (3.5, 3.5), "H2": (3.5, CT_H - 3.5), "H3": (88.0, 3.5), "H4": (88.0, CT_H - 3.5)}.items():
        P[r] = (x, y, 0)
    return P

if __name__ == "__main__":
    e1, _ = build("main_board", "main_board.kicad_sch", (MAIN_W, MAIN_H), main_place(),
                  texts=[("POWER MONITOR rev 0 - 24.0 V MAX", 40.0, 66.5, 1.5)])
    e2, _ = build("ct_board", "ct_board.kicad_sch", (CT_W, CT_H), ct_place(),
                  texts=[("NO MAINS COPPER - single L wire through each CT", 4.0, 31.5, 1.2)])
    sys.exit(1 if e1 or e2 else 0)
