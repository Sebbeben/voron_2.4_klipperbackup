#!/usr/bin/env python3
"""Export BOM CSVs from the schematics.

<board>_bom_jlcpcb.csv     - SMD parts only, for JLCPCB assembly (Comment, Designator, Footprint, LCSC, MPN, Qty)
<board>_hand_solder.csv    - THT parts (mounted on the back and soldered by hand) - order from LCSC
Through-hole is decided from the footprint itself (thru_hole pads), not from the reference.
"""
import re, csv, os, sys, collections
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_pcb import fp_text

def is_tht(fp):
    try:
        return " thru_hole " in fp_text(fp)
    except OSError:
        return False

for board in ("main_board", "ct_board"):
    t = open(os.path.join(HERE, board + ".kicad_sch")).read()
    groups = {"smd": collections.OrderedDict(), "tht": collections.OrderedDict()}
    for m in re.finditer(r'\(symbol \(lib_id "([^"]+)"\)(.*?)\(instances', t, re.S):
        body = m.group(2)
        prop = lambda k: (re.search(r'\(property "%s" "([^"]*)"' % k, body) or [None, ""])[1]
        ref = prop("Reference")
        fp = prop("Footprint")
        if ref.startswith("#") or "(dnp yes)" in body or "(in_bom no)" in body or fp.startswith("MountingHole") \
           or fp.startswith("TestPoint"):
            continue
        key = (prop("Value"), fp, prop("LCSC"), prop("MPN"))
        groups["tht" if is_tht(fp) else "smd"].setdefault(key, []).append(ref)
    for kind, suffix in (("smd", "_bom_jlcpcb.csv"), ("tht", "_hand_solder.csv")):
        out = os.path.join(HERE, board + suffix)
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "MPN", "Qty"])
            for (val, fp, lcsc, mpn), refs in groups[kind].items():
                refs.sort(key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0)))
                w.writerow([val, ",".join(refs), fp.split(":")[-1], lcsc, mpn, len(refs)])
        print("wrote", os.path.basename(out), len(groups[kind]), "lines,", sum(len(v) for v in groups[kind].values()), "parts")
