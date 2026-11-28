#!/usr/bin/env python3
"""One calibration plate for a filament: flow tiles, pressure advance lines, retraction towers,
bridges (10-50 mm at the Orca bridge flow 0.95), max volumetric flow (one cylinder) and - last, because it is tall - a temperature tower.

Every test is one connected piece standing on a one-layer web with raised labels (values and a
title with the material), placed on a free spot by calib_common.find_spot. The sections are
joined into one gcode file in the gcodes folder; each section homes, levels, meshes its own area
and purges in front of itself (see calib_common.start_gcode). Start the file like any other print.

Usage:  calib_plate.py MATERIAL [--name LABEL] [--reset] [--no-temp] [--only flow,pa,...]
        calib_plate.py --list
  MATERIAL  one of MATERIALS below (ABS, PLA, PETG, TPU, NYLON, POM)
  --reset   the plate has been cleared: forget the old layout first
  --name    text on the labels instead of the material key (max ~6 characters)
Klipper: CALIB_PLATE MATERIAL=PETG [RESET=1] [TEMP=0] (tools/calib_plate.cfg).

The values are generic start points for the material class. Check them against the spool
(printed temperature range) and adjust with --temp / --bed before printing an unknown brand.
"""
import argparse, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calib_common as cc

TOOLS = os.path.dirname(os.path.abspath(__file__))
GCODES = os.path.expanduser("~/printer_data/gcodes")

# temp/bed = print values; first_* = first layer; fan %; flow = assumed flow ratio for all tests
# except the flow tiles; speed = M220 % for flow/PA/retraction/temp tower (max flow is volumetric
# and always runs at 100 %); note = shown at the start of the print.
MATERIALS = {
    "ABS": dict(temp=250, first_temp=255, bed=105, first_bed=110, fan=20, bridge_fan=60, flow=0.99, speed=100,
                flow_tiles=(0.92, 1.06), pa=(0.02, 0.08, 0.005), ret=(0.2, 1.2, 0.2),
                maxflow=(14, 28, 2), tower=(265, 235, 5),
                note="Closed chamber."),
    "PLA": dict(temp=215, first_temp=220, bed=60, first_bed=65, fan=100, bridge_fan=100, flow=0.98, speed=100,
                flow_tiles=(0.90, 1.04), pa=(0.01, 0.07, 0.005), ret=(0.2, 1.2, 0.2),
                maxflow=(10, 24, 2), tower=(230, 200, 5),
                note="DOOR AND LID OPEN - a warm chamber gives heat creep with PLA."),
    "PETG": dict(temp=240, first_temp=245, bed=80, first_bed=85, fan=40, bridge_fan=50, flow=0.97, speed=80,
                 flow_tiles=(0.90, 1.04), pa=(0.02, 0.08, 0.005), ret=(0.2, 1.2, 0.2),
                 maxflow=(8, 22, 2), tower=(255, 225, 5),
                 note="Door closed, lid ajar. PETG sticks hard to PEI - let the plate cool before removing."),
    "TPU": dict(temp=225, first_temp=230, bed=50, first_bed=55, fan=50, bridge_fan=60, flow=1.0, speed=30,
                flow_tiles=(0.92, 1.06), pa=(0.0, 0.24, 0.02), ret=(0.0, 1.0, 0.2),
                maxflow=(2, 9, 1), tower=(240, 210, 5),
                note="TPU 95A: slow (30 % speed). Loosen the Orbiter tension a little if it buckles."),
    "NYLON": dict(temp=255, first_temp=260, bed=90, first_bed=95, fan=10, bridge_fan=40, flow=0.98, speed=70,
                  flow_tiles=(0.92, 1.06), pa=(0.02, 0.08, 0.005), ret=(0.2, 1.2, 0.2),
                  maxflow=(6, 13, 1), tower=(275, 245, 5),
                  note="DRY THE SPOOL FIRST (wet nylon foams and strings). Glue stick on the plate, chamber closed."),
    "POM": dict(temp=215, first_temp=220, bed=110, first_bed=110, fan=10, bridge_fan=40, flow=0.98, speed=70,
                flow_tiles=(0.92, 1.06), pa=(0.02, 0.08, 0.005), ret=(0.2, 1.2, 0.2),
                maxflow=(6, 13, 1), tower=(230, 200, 5),
                note="POM barely sticks to PEI: use a POM/PP build sheet or glue, chamber closed."),
}

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("material", nargs="?")
p.add_argument("--name", default=None)
p.add_argument("--reset", action="store_true", help="plate cleared: forget the old bed layout")
p.add_argument("--no-temp", action="store_true", help="leave out the temperature tower")
p.add_argument("--no-bridge", action="store_true", help="leave out the bridge test")
p.add_argument("--only", default="", help="comma list of flow,pa,ret,bridge,maxflow,temp")
p.add_argument("--temp", type=int, help="override the print temperature")
p.add_argument("--bed", type=int, help="override the bed temperature")
p.add_argument("--outdir", default=GCODES)
p.add_argument("--list", action="store_true")
a = p.parse_args()

if a.list or not a.material:
    for k, m in MATERIALS.items():
        print(f"{k:6} {m['temp']} C, bed {m['bed']}, tower {m['tower'][0]}->{m['tower'][1]}, "
              f"max flow {m['maxflow'][0]}-{m['maxflow'][1]} mm3/s. {m['note']}")
    sys.exit(0)
key = a.material.upper()
if key not in MATERIALS:
    sys.exit(f"Unknown material {a.material} - choose one of {', '.join(MATERIALS)}")
m = dict(MATERIALS[key])
if a.temp:
    m["first_temp"] += a.temp - m["temp"]; m["temp"] = a.temp
if a.bed:
    m["first_bed"] += a.bed - m["bed"]; m["bed"] = a.bed
name = (a.name or key)[:7]
only = set(x.strip() for x in a.only.split(",") if x.strip()) or {"flow", "pa", "ret", "bridge", "maxflow", "temp"}
if a.no_temp:
    only.discard("temp")
if a.no_bridge:
    only.discard("bridge")

if a.reset:
    cc.reset_layout()
stamp = time.strftime("%Y%m%d_%H%M")
# per-test files go outside the gcodes list and outside the backed-up config folder
work = os.path.join(os.path.expanduser("~/printer_data/calib_work"), f"calib_{key}_{stamp}")
os.makedirs(work, exist_ok=True)
T, B = str(m["temp"]), str(m["bed"])
common = ["--bed", B, "--first-bed", str(m["first_bed"]), "--name", name]
fl, fh = m["flow_tiles"]
jobs = [   # (key, script, args, speed %)
    ("flow", "gen_flow_tiles.py", ["--start", str(fl), "--end", str(fh), "--step", "0.01", "--temp", T,
                                   "--first-temp", str(m["first_temp"]), "--fan", str(m["fan"])], m["speed"]),
    ("pa", "gen_pa_lines.py", ["--start", str(m["pa"][0]), "--end", str(m["pa"][1]), "--step", str(m["pa"][2]),
                               "--temp", T, "--first-temp", str(m["first_temp"]), "--flow", str(m["flow"])], m["speed"]),
    ("bridge", "gen_bridge.py", ["--temp", T, "--first-temp", str(m["first_temp"]), "--flow", str(m["flow"]),
                                 "--fan", str(m["fan"]), "--bridge-fan", str(m["bridge_fan"]), "--flows", "0.95"], m["speed"]),
    ("ret", "gen_retract.py", ["--start", str(m["ret"][0]), "--end", str(m["ret"][1]), "--step", str(m["ret"][2]),
                               "--temp", T, "--first-temp", str(m["first_temp"]), "--flow", str(m["flow"]),
                               "--fan", str(m["fan"])], m["speed"]),
    ("maxflow", "gen_max_flow.py", ["--start", str(m["maxflow"][0]), "--end", str(m["maxflow"][1]),
                                    "--step", str(m["maxflow"][2]), "--temp", T, "--first-temp", str(m["first_temp"]),
                                    "--flow", str(m["flow"]), "--fan", str(m["fan"])], 100),
    ("temp", "gen_temp_tower.py", ["--hot", str(m["tower"][0]), "--cold", str(m["tower"][1]),
                                   "--step", str(m["tower"][2]), "--flow", str(m["flow"]), "--fan", str(m["fan"])],
     m["speed"]),
]
sections, report = [], []
for k, script, args, speed in jobs:
    if k not in only:
        continue
    out = os.path.join(work, f"{len(sections) + 1}_{k}.gcode")
    args = args + common
    r = subprocess.run([sys.executable, os.path.join(TOOLS, script), out] + args, capture_output=True, text=True)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().splitlines()
        report.append(f"{k}: SKIPPED - {msg[-1] if msg else 'error'}")
        continue
    report.append(f"{k}: " + r.stdout.strip().splitlines()[0].split(": ", 1)[-1])
    sections.append((k, out, speed))

if not sections:
    print("\n".join(report))
    sys.exit("Nothing fits on the plate - clear it and use --reset / RESET=1")

final = os.path.join(a.outdir, f"calib_{key}_{stamp}.gcode")
with open(final, "w") as f:
    f.write(f"; Calibration plate {key} ({name}) {stamp} - generated by calib_plate.py\n")
    f.write(f"; {m['temp']} C (first {m['first_temp']}), bed {m['bed']} (first {m['first_bed']}), "
            f"fan {m['fan']} %, assumed flow {m['flow']}, speed {m['speed']} %\n")
    for line in report:
        f.write(f"; {line}\n")
    f.write(f'RESPOND TYPE=command MSG="Calibration plate {key}: {m["note"]}"\n')
    for k, path, speed in sections:
        f.write(f"\n; ======== {os.path.basename(path)} ========\n")
        f.write("EXCLUDE_OBJECT_DEFINE RESET=1        ; adaptive mesh only over this section's objects\n")
        f.write(f'RESPOND MSG="Calibration {key}: {k}"\n')
        f.write(f"M220 S{speed}\n")
        f.write(open(path).read())
    f.write("\n; ======== end of plate ========\nM220 S100\nTURN_OFF_HEATERS\nM107\nM84\n"
            "SET_IDLE_TIMEOUT TIMEOUT=1800\n"
            f'RESPOND MSG="Calibration plate {key} done - heaters off"\n')
print(f"{os.path.basename(final)} written ({len(sections)} tests)")
for line in report:
    print("  " + line)
print("  " + m["note"])
