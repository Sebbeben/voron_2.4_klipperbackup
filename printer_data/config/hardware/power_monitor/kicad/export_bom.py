#!/usr/bin/env python3
"""Export a JLCPCB-style BOM CSV (Comment, Designator, Footprint, LCSC, MPN) from the schematics."""
import re, csv, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
for board in ("main_board", "ct_board"):
    t = open(os.path.join(HERE, board + ".kicad_sch")).read()
    groups = collections.OrderedDict()
    for m in re.finditer(r'\(symbol \(lib_id "([^"]+)"\)(.*?)\(instances', t, re.S):
        body = m.group(2)
        prop = lambda k: (re.search(r'\(property "%s" "([^"]*)"' % k, body) or [None, ""])[1]
        ref = prop("Reference")
        if ref.startswith("#") or "(dnp yes)" in body or prop("Footprint").startswith("MountingHole") \
           or prop("Footprint").startswith("TestPoint"):
            continue
        key = (prop("Value"), prop("Footprint"), prop("LCSC"), prop("MPN"))
        groups.setdefault(key, []).append(ref)
    out = os.path.join(HERE, board + "_bom_jlcpcb.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "MPN", "Qty"])
        for (val, fp, lcsc, mpn), refs in groups.items():
            refs.sort(key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0)))
            w.writerow([val, ",".join(refs), fp.split(":")[-1], lcsc, mpn, len(refs)])
    print("wrote", out, len(groups), "lines")
