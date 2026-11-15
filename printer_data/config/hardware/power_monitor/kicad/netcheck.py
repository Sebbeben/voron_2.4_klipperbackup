#!/usr/bin/env python3
"""Extract the netlist from a generated .kicad_sch (labels, wires, junctions, pin ends).

Used to prove that a re-layout of gen_schematic.py does not change connectivity:
    python3 netcheck.py main_board.kicad_sch > a.txt   (before)
    python3 netcheck.py main_board.kicad_sch > b.txt   (after);  diff a.txt b.txt
Rules (as KiCad): points that coincide are connected; a wire connects every point
that lies on it (pin end, label, other wire end); labels with the same text are one net.
Also reports pins left unconnected (no wire, label or no-connect flag).
"""
import math, re, sys, collections
sys.dont_write_bytecode = True
import kilib

def rnd(v):
    return round(v * 100) / 100

def parse(path):
    t = open(path).read()
    libs = {}
    ls = t.index("(lib_symbols")
    lb = kilib._block(t, ls)
    pos = 0
    while True:
        i = lb.find('(symbol "', pos)
        if i < 0:
            break
        blk = kilib._block(lb, i)
        name = re.match(r'\(symbol "([^"]+)"', blk).group(1)
        libs[name] = kilib.pins(blk)
        pos = i + len(blk)
    body = t[:ls] + t[ls + len(lb):]
    pins = []      # (ref, num, x, y)
    for m in re.finditer(r'\(symbol \(lib_id "([^"]+)"\) \(at ([-\d.]+) ([-\d.]+) (\d+)\)', body):
        blk = kilib._block(body, m.start())
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk).group(1)
        x, y, a = float(m.group(2)), float(m.group(3)), int(m.group(4))
        c, s = round(math.cos(math.radians(a))), round(math.sin(math.radians(a)))
        for num, (name, px, py, pa, et) in libs[m.group(1)].items():
            rx, ry = px * c - py * s, px * s + py * c
            pins.append((ref, num, rnd(x + rx), rnd(y - ry), et, name))
    labels = [(n, rnd(float(x)), rnd(float(y))) for n, x, y in
              re.findall(r'\(label "([^"]+)" \(at ([-\d.]+) ([-\d.]+)', body)]
    wires = []
    for m in re.finditer(r'\(wire \(pts \(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)\)', body):
        wires.append(tuple(rnd(float(v)) for v in m.groups()))
    ncs = {(rnd(float(x)), rnd(float(y))) for x, y in re.findall(r'\(no_connect \(at ([-\d.]+) ([-\d.]+)\)', body)}
    return pins, labels, wires, ncs

def on_seg(p, w):
    (x, y), (x1, y1, x2, y2) = p, w
    if min(x1, x2) - 0.01 <= x <= max(x1, x2) + 0.01 and min(y1, y2) - 0.01 <= y <= max(y1, y2) + 0.01:
        return abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) < 0.01
    return False

def netlist(path):
    pins, labels, wires, ncs = parse(path)
    parent = {}
    def f(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def u(a, b):
        parent[f(a)] = f(b)
    pts = {(p[2], p[3]) for p in pins} | {(l[1], l[2]) for l in labels}
    for w in wires:
        pts |= {(w[0], w[1]), (w[2], w[3])}
    for w in wires:
        a = ("P", w[0], w[1])
        for p in pts:
            if on_seg(p, w):
                u(("P",) + p, a)
    for n, x, y in labels:
        u(("P", x, y), ("L", n))
    nets = collections.defaultdict(set)
    named = collections.defaultdict(set)
    for ref, num, x, y, et, name in pins:
        if ref.startswith("#"):
            continue
        nets[f(("P", x, y))].add("%s.%s" % (ref, num))
    for n, x, y in labels:
        named[f(("L", n))].add(n)
    out = []
    for root, members in nets.items():
        names = sorted(named.get(root, []))
        out.append((",".join(names) or "?", sorted(members)))
    # unconnected pins: alone in their net, no label, no NC flag
    lonely = []
    for ref, num, x, y, et, name in pins:
        if ref.startswith("#") or et == "no_connect":
            continue
        root = f(("P", x, y))
        if (x, y) in ncs:
            continue
        if len(nets[root]) < 2 and not named.get(root):
            lonely.append("%s.%s" % (ref, num))
    return sorted(out), sorted(lonely)

if __name__ == "__main__":
    nets, lonely = netlist(sys.argv[1])
    for name, members in nets:
        print(name, ":", " ".join(members))
    print("# nets:", len(nets))
    print("# unconnected pins:", " ".join(lonely) or "none")
    multi = [n for n, m in nets if "," in n]
    print("# nets with more than one label name (shorts?):", " ".join(multi) or "none")
