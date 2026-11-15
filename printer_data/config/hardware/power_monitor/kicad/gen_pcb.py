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
        if not c.startswith("(fp_") or ('(layer "F.CrtYd")' not in c and '(layer "B.CrtYd")' not in c):
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

def _num(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s

def flip_text(t):
    """Mirror a footprint to the back side (KiCad top/bottom flip in local coordinates):
    y -> -y, local angles negated (done in fp_block), F.* layers -> B.*, texts mirrored."""
    t = re.sub(r'\((at|start|end|center|mid|xy) ([-\d.]+) ([-\d.]+)',
               lambda m: "(%s %s %s" % (m.group(1), m.group(2), _num(-float(m.group(3)))), t)
    t = re.sub(r'"F\.(SilkS|Fab|CrtYd|Paste|Mask|Cu|Adhes)"', r'"B.\1"', t)
    out, pos = [], 0
    while True:
        k = t.find("(effects", pos)
        if k < 0:
            break
        blk = kilib._block(t, k)
        if "mirror" not in blk:
            if "(justify" in blk:
                nb = re.sub(r'\(justify ([^)]*)\)', r'(justify \1 mirror)', blk, 1)
            else:
                nb = blk[:-1] + " (justify mirror))"
        else:
            nb = blk
        out.append(t[pos:k] + nb)
        pos = k + len(blk)
    out.append(t[pos:])
    return "".join(out)

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
# Main board placement: (courtyard centre x, y in mm from the board top-left corner as seen from
# the TOP (SMD) side, rotation, side). Side "B" = through-hole parts on the back, hand-soldered;
# the board is mounted with the back (THT side: terminals, fuses, LEDs) facing out.
# --------------------------------------------------------------------------
# Top side (JLC SMT): shunts sit between the two fuse-clip pad rows of their column, INA3221 +
# filter row above the 24V_BUS band (F.Cu pour, y ~44-48), MCU / mains analog / relay driver in
# the upper part over the back-side connectors (never on a THT pad, 1 mm soldering clearance).
# Back side: 7 output terminals on the bottom edge, fuse (2 clips, 9.73 mm) + 3 mm LED per column,
# inputs on the left/right edges, relay coil / Pi / alert / AC jack / RJ45 on the top edge.
MAIN_W, MAIN_H = 100.0, 80.0
PITCH = 12.8
COL = [11.55 + PITCH * k for k in range(7)]      # output columns F1..F7
def main_place():
    H = MAIN_H
    P = {}
    shunts = ["RS2", "RS3", "RS4", "RS5", "RS6", "RS7", "RS9"]
    for k, x in enumerate(COL):
        n = k + 1
        P["J%d" % (n + 2)] = (x, H - 5.4, 180, "B")        # wire entry down
        P["F%dB" % n] = (x, H - 13.7, 270, "B")            # load-side clip
        P["F%dA" % n] = (x, H - 13.7 - 9.73, 270, "B")     # supply-side clip (ATM = 9.73 mm)
        P["LEDF%d" % n] = (x, H - 29.4, 0, "B")             # blown-fuse LED, visible next to the fuse
        P[shunts[k]] = (x, H - 18.57, 0)                    # top side, between the clip pad rows
        P["RL%d" % n] = (x + (4.6 if k < 6 else -4.6), H - 29.4, 90)   # RL7 left: H4 hole
    # 24 V input (left edge) / 5 V input (right edge), wire entry outward
    P["J1"] = (5.4, 38.0, 90, "B")
    P["D1"] = (10.5, 38.0, 90)
    P["RS1"] = (15.0, 38.0, 270)
    P["C14"] = (20.0, 46.0, 0)
    P["C15"] = (26.0, 46.0, 0)
    P["J2"] = (MAIN_W - 5.4, 38.0, 270, "B")
    P["D2"] = (89.0, 46.0, 0)
    P["RS8"] = (86.5, 38.0, 270)
    P["C16"] = (80.0, 46.0, 0)
    # INA row + filter triplets (R IN+ side, C, R IN- side per channel)
    for i, (u, x) in enumerate((("U1", 30.0), ("U2", 50.0), ("U3", 70.0))):
        P[u] = (x, 35.0, 0)
        P["C%d" % (10 + i)] = (x + 5.0, 32.5, 90)
    for ch in range(1, 10):
        x = 22.0 + (ch - 1) * 7.4
        P["R%d" % (2 * ch - 1)] = (x - 2.2, 41.0, 90)
        P["C%d" % ch] = (x, 41.0, 90)
        P["R%d" % (2 * ch)] = (x + 2.2, 41.0, 90)
    # back side, top edge connectors (openings up)
    P["J12"] = (13.5, 5.4, 0, "B")                      # relay coil
    P["J10"] = (30.0, 3.5, 0, "B")                      # Pi header
    P["J11"] = (45.0, 3.5, 0, "B")                      # alert out
    P["J21"] = (58.0, 8.0, 270, "B")                    # AC jack
    P["J20"] = (77.0, 9.4, 0, "B")                      # RJ45
    P["J22"] = (24.5, 14.0, 0, "B")                     # SWD header
    P["LED11"] = (8.0, 25.0, 0, "B")                    # relay energised
    P["LED10"] = (54.0, 28.0, 0, "B")                   # MCU status
    # relay driver (top)
    P["F8"] = (3.0, 15.0, 90)
    P["D15"] = (7.5, 15.5, 90)
    P["R87"] = (11.5, 14.0, 90)
    P["Q1"] = (15.5, 14.5, 0)
    P["Q2"] = (15.5, 21.0, 0)
    P["R83"] = (20.0, 13.0, 90)
    P["R84"] = (20.0, 17.0, 90)
    P["R85"] = (20.0, 21.0, 90)
    P["R86"] = (20.0, 25.0, 90)
    # Pi pull-ups + test points
    for i, r in enumerate(["R19", "R20", "R21", "R22"]):
        P[r] = (28.5 + i * 2.0, 9.0, 90)
    for i, r in enumerate(["TP7", "TP8", "TP9", "TP10"]):
        P[r] = (41.5 + i * 3.0, 10.0, 0)
    # MCU (top)
    P["U10"] = (40.0, 20.0, 0)
    P["C40"] = (32.5, 13.0, 90)
    P["C41"] = (34.5, 13.0, 90)
    P["C42"] = (36.5, 13.0, 90)
    P["C43"] = (33.8, 19.0, 90)
    P["SW1"] = (29.5, 23.0, 90)
    P["FB1"] = (33.0, 27.5, 0)
    P["R60"] = (48.0, 15.0, 0)
    P["R61"] = (48.0, 17.5, 0)
    P["R62"] = (48.0, 20.0, 0)
    P["R64"] = (48.0, 23.0, 0)
    P["JP1"] = (48.0, 26.0, 0)
    P["R65"] = (44.0, 28.0, 0)
    P["TP4"] = (36.5, 29.5, 0)
    P["TP5"] = (39.5, 29.5, 0)
    # mains analog (top), over the AC jack / RJ45 bodies but clear of their pins
    P["R72"] = (57.0, 20.5, 90)
    P["R73"] = (59.0, 20.5, 90)
    for i in range(5):
        x = 62.0 + i * 5.2
        P["R%d" % (74 + i)] = (x - 1.0, 20.5, 90)
        P["C%d" % (35 + i)] = (x + 1.0, 20.5, 90)
        P["D%d" % (10 + i)] = (x, 25.5, 0)
        if i < 4:
            P["R%d" % (79 + i)] = (x, 29.5, 90)
    P["R70"] = (89.0, 20.0, 90)
    P["R71"] = (91.0, 20.0, 90)
    P["C30"] = (93.0, 20.0, 90)
    P["C31"] = (95.0, 20.0, 90)
    P["TP6"] = (97.5, 23.0, 0)
    # 3V3 LDO (AMS1117, SOT-223) next to the 5 V input
    P["U12"] = (91.5, 28.5, 0)
    P["C17"] = (85.5, 32.0, 90)
    P["C13"] = (97.6, 28.5, 90)
    # test points on the power rails
    P["TP1"] = (12.5, 32.0, 0)
    P["TP2"] = (31.0, 46.0, 0)
    P["TP3"] = (74.5, 46.0, 0)
    # mounting holes
    for r, (x, y) in {"H1": (3.5, 3.5), "H2": (MAIN_W - 3.5, 3.5),
                      "H3": (3.5, 48.0), "H4": (MAIN_W - 3.5, 48.0)}.items():
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
                  texts=[("POWER MONITOR rev 0 - 24.0 V MAX", 36.0, 29.5, 1.0)])
    e2, _ = build("ct_board", "ct_board.kicad_sch", (CT_W, CT_H), ct_place(),
                  texts=[("NO MAINS COPPER - single L wire through each CT", 9.0, 23.0, 1.0)])
    sys.exit(1 if e1 or e2 else 0)
