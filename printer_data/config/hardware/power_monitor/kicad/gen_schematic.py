#!/usr/bin/env python3
"""Generate the KiCad 8 schematics for the power monitor (main board + CT board).

Parts inside a block are connected with wires (signal flow left to right); net labels
join the blocks. Re-run after editing, then prove the connectivity did not change:
    python3 gen_schematic.py
    python3 netcheck.py main_board.kicad_sch   (compare with the previous output)
Symbols come from the official KiCad 8.0.8 libraries in ./libsrc, plus a
custom INA3221 symbol defined here (not in the KiCad library).
"""
import math, os, re, sys, uuid
sys.dont_write_bytecode = True  # keep __pycache__ out of the config backup
import kilib

HERE = os.path.dirname(os.path.abspath(__file__))
DATE = "2026-11-14"

def U():
    return str(uuid.uuid4())

def sym_uuid(project, ref):
    """Stable symbol UUID, so the PCB (gen_pcb.py) stays linked to the schematic after re-generation."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "powermonitor/%s/%s" % (project, ref)))

W = "~"  # net placeholder: pin is connected by a wire drawn by the caller

# --------------------------------------------------------------------------
# Custom INA3221 symbol (pinout from TI datasheet SBOS576C, RGV package)
# --------------------------------------------------------------------------
INA_PINS = [  # number, name, type, side, slot
    ("12", "IN+1", "input", "L", 0), ("11", "IN-1", "input", "L", 1),
    ("15", "IN+2", "input", "L", 3), ("14", "IN-2", "input", "L", 4),
    ("2", "IN+3", "input", "L", 6), ("1", "IN-3", "input", "L", 7),
    ("4", "VS", "power_in", "R", 0), ("16", "VPU", "power_in", "R", 1),
    ("5", "A0", "input", "R", 2), ("6", "SCL", "input", "R", 3),
    ("7", "SDA", "bidirectional", "R", 4), ("8", "Warning", "open_collector", "R", 5),
    ("9", "Critical", "open_collector", "R", 6), ("10", "PV", "open_collector", "R", 7),
    ("13", "TC", "open_collector", "R", 8),
    ("3", "GND", "power_in", "B", 0), ("17", "EP", "passive", "B", 1),
]

# STM32G071KxT (GP version, no N suffix) differs from the KxTxN (PD version) that KiCad has a
# symbol for: DS12232 Rev 3 figure 7. Only the in-stock KBT6 (C529348) is a GP part.
GP_PIN_NAMES = {"17": "PB2", "26": "PA15", "27": "PB3", "28": "PB4", "29": "PB5"}

def stm32_gp_symbol():
    b = kilib.flat_symbol("MCU_ST_STM32G0", "STM32G071KBTxN")
    b = b.replace('(symbol "MCU_ST_STM32G0:STM32G071KBTxN"', '(symbol "PowerMonitor:STM32G071KBTx"', 1)
    b = b.replace('(symbol "STM32G071KBTxN_', '(symbol "STM32G071KBTx_')
    out, pos = [], 0
    for m in kilib.PIN_RE.finditer(b):
        pb = kilib._block(b, m.start())
        num = re.search(r'\(number "([^"]*)"', pb).group(1)
        if num in GP_PIN_NAMES:
            new = re.sub(r'\(name "[^"]*"', '(name "%s"' % GP_PIN_NAMES[num], pb, 1)
            out.append(b[pos:m.start()] + new)
            pos = m.start() + len(pb)
    out.append(b[pos:])
    b = "".join(out)
    b = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "STM32G071KBTx"', b, 1)
    b = re.sub(r'\(property "Description" "[^"]*"', '(property "Description" "STM32G071KBT6 LQFP-32 GP version (DS12232 fig. 7): pin 17 PB2, 26-29 PA15/PB3/PB4/PB5"', b, 1)
    return b

def ct_symbol():
    b = kilib.flat_symbol("Device", "Transformer_1P_1S")
    b = b.replace('(symbol "Device:Transformer_1P_1S"', '(symbol "PowerMonitor:ZMCT103C"', 1)
    b = b.replace('(symbol "Transformer_1P_1S_', '(symbol "ZMCT103C_')
    out, pos = [], 0
    for m in kilib.PIN_RE.finditer(b):
        pb = kilib._block(b, m.start())
        num = re.search(r'\(number "([^"]*)"', pb).group(1)
        if num in ("1", "2"):          # primary pins do not exist: the mains wire goes through the hole
            out.append(b[pos:m.start()])
            pos = m.start() + len(pb)
    out.append(b[pos:])
    b = "".join(out)
    b = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "ZMCT103C"', b, 1)
    b = re.sub(r'\(property "Footprint" "[^"]*"', '(property "Footprint" "PowerMonitor:ZMCT103C"', b, 1)
    b = re.sub(r'\(property "Description" "[^"]*"', '(property "Description" "ZMCT103C 1000:1 wire-through CT; only the secondary (pins 3/4) has pads"', b, 1)
    return b

def ina_symbol():
    pins = []
    for num, name, typ, side, slot in INA_PINS:
        if side == "L":
            x, y, a = -15.24, 10.16 - slot * 2.54, 0
        elif side == "R":
            x, y, a = 15.24, 10.16 - slot * 2.54, 180
        else:
            x, y, a = -1.27 + slot * 2.54, -15.24, 90
        pins.append(
            '(pin %s line (at %g %g %d) (length 2.54) (name "%s" (effects (font (size 1.27 1.27)))) '
            '(number "%s" (effects (font (size 1.27 1.27)))))' % (typ, x, y, a, name, num))
    return (
        '(symbol "PowerMonitor:INA3221" (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
        '(property "Reference" "U" (at -12.7 13.97 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        '(property "Value" "INA3221" (at 2.54 13.97 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        '(property "Footprint" "Package_DFN_QFN:Texas_RGV0016A_VQFN-16-1EP_4x4mm_P0.65mm_EP2.1x2.1mm" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '(property "Datasheet" "https://www.ti.com/lit/ds/symlink/ina3221.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '(property "Description" "Triple-channel shunt and bus voltage monitor, I2C, 0-26 V" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '(symbol "INA3221_0_1" (rectangle (start -12.7 12.7) (end 12.7 -12.7) (stroke (width 0.254) (type default)) (fill (type background))))\n'
        '(symbol "INA3221_1_1" %s))' % " ".join(pins))

# --------------------------------------------------------------------------
# Schematic builder
# --------------------------------------------------------------------------
class Sheet:
    def __init__(self, project, title, paper, comment):
        self.project, self.title, self.paper, self.comment = project, title, paper, comment
        self.root = str(uuid.uuid5(uuid.NAMESPACE_URL, "powermonitor/" + project))   # stable across runs
        self.libs = {}       # lib_id -> block
        self.items = []
        self.refs = set()
        self.pwr = 0

    def lib(self, lib_id):
        if lib_id not in self.libs:
            if lib_id == "PowerMonitor:INA3221":
                self.libs[lib_id] = ina_symbol()
            elif lib_id == "PowerMonitor:TVS_Uni":
                self.libs[lib_id] = tvs_uni_symbol()
            elif lib_id == "PowerMonitor:ZMCT103C":
                self.libs[lib_id] = ct_symbol()
            elif lib_id == "PowerMonitor:STM32G071KBTx":
                self.libs[lib_id] = stm32_gp_symbol()
            else:
                lib, name = lib_id.split(":")
                self.libs[lib_id] = kilib.flat_symbol(lib, name)
        return self.libs[lib_id]

    def pins(self, lib_id):
        return kilib.pins(self.lib(lib_id))

    def label(self, net, x, y, pin_angle):
        la = {0: 180, 180: 0, 90: 270, 270: 90}[pin_angle]
        just = "left bottom" if la in (0, 90) else "right bottom"
        self.items.append(
            '(label "%s" (at %.2f %.2f %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify %s)) (uuid "%s"))'
            % (net, x, y, la, just, U()))

    def nc(self, x, y):
        self.items.append('(no_connect (at %.2f %.2f) (uuid "%s"))' % (x, y, U()))

    def text(self, s, x, y, size=2.54, bold=True):
        self.items.append(
            '(text "%s" (exclude_from_sim no) (at %.2f %.2f 0) (effects (font (size %g %g)%s) (justify left bottom)) (uuid "%s"))'
            % (s.replace('"', "'"), x, y, size, size, " (bold yes)" if bold else "", U()))

    def note(self, lines, x, y, size=1.5):
        """Multi-line plain note (design calculations). KiCad reads \\n as a line break."""
        self.text("\\n".join(lines), x, y, size, bold=False)

    def part(self, lib_id, ref, value, x, y, nets, footprint=None, lcsc="", mpn="", dnp=False, note="",
             in_bom=True, rot=0, fields=None, hide_val=False):
        """nets: {pin_number: net_name, W (= wired by the caller) or None (= no-connect)}.
        Unlisted pins -> no-connect. rot = 0/90/180/270 (counter-clockwise).
        Returns {pin_number: (x, y)} of the pin ends in sheet coordinates."""
        assert ref not in self.refs, ref
        self.refs.add(ref)
        block = self.lib(lib_id)
        if footprint is None:
            m = re.search(r'\(property "Footprint" "([^"]*)"', block)
            footprint = m.group(1) if m else ""
        pins = kilib.pins(block)
        ends = self.pin_ends(lib_id, x, y, rot)
        hide = "(hide yes)"
        fa = 90 if rot in (90, 270) else 0          # KiCad swaps H/V field text on 90/270 symbols
        if fields is None:
            pts = list(ends.values())
            horizontal = len(pts) == 2 and abs(pts[0][0] - pts[1][0]) > 0.1
            if len(pts) == 2 and horizontal:
                fields = ((0, -2.54, "center"), (0, 2.54, "center"))
            elif len(pts) == 2:
                fields = ((2.54, -1.27, "left"), (2.54, 1.27, "left")) if rot == 0 else \
                         ((5.08, -1.27, "center"), (5.08, 1.27, "center"))
            else:
                fields = ((2.54, -1.27, "left"), (2.54, 1.27, "left"))
        (rdx, rdy, rj), (vdx, vdy, vj) = fields
        props = [
            ('Reference', ref, rdx, rdy, rj, ""), ('Value', value, vdx, vdy, vj, hide if hide_val else ""),
            ('Footprint', footprint, 0, 0, "left", hide), ('Datasheet', "~", 0, 0, "left", hide),
            ('Description', note, 0, 0, "left", hide), ('LCSC', lcsc, 0, 0, "left", hide), ('MPN', mpn, 0, 0, "left", hide),
        ]
        if ref.startswith("#"):
            props = [('Reference', ref, 0, 2.54, "center", hide), ('Value', value, 0, -2.54, "center", hide)]
        ptxt = " ".join(
            '(property "%s" "%s" (at %.2f %.2f %d) (effects (font (size 1.27 1.27))%s %s))'
            % (k, v, x + dx, y + dy, fa, "" if j == "center" else " (justify %s)" % j, h) for k, v, dx, dy, j, h in props)
        pin_txt = " ".join('(pin "%s" (uuid "%s"))' % (n, U()) for n in pins)
        self.items.append(
            '(symbol (lib_id "%s") (at %.2f %.2f %d) (unit 1) (exclude_from_sim no) (in_bom %s) (on_board yes) (dnp %s) (uuid "%s") %s %s '
            '(instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))'
            % (lib_id, x, y, rot, "no" if ref.startswith("#") or not in_bom else "yes", "yes" if dnp else "no",
               sym_uuid(self.project, ref), ptxt, pin_txt,
               self.project, self.root, ref))
        for num, (name, px, py, pa, etype) in pins.items():
            ax, ay, aa = ends[num]
            net = nets.get(num, nets.get(name, "__NC__"))
            if etype == "no_connect" or net == W:
                continue
            if net in (None, "__NC__"):
                self.nc(ax, ay)
            else:
                self.label(net, ax, ay, aa)
        return {k: (v[0], v[1]) for k, v in ends.items()}

    def pin_ends(self, lib_id, x, y, rot):
        c, s = round(math.cos(math.radians(rot))), round(math.sin(math.radians(rot)))
        out = {}
        for num, (name, px, py, pa, etype) in kilib.pins(self.lib(lib_id)).items():
            rx, ry = px * c - py * s, px * s + py * c
            out[num] = (round(x + rx, 2), round(y - ry, 2), (pa + rot) % 360)
        return out

    def put(self, lib_id, ref, value, pin, px, py, nets, rot=0, **kw):
        """Place a symbol so that `pin` ends exactly at (px, py)."""
        e = self.pin_ends(lib_id, 0, 0, rot)[pin]
        return self.part(lib_id, ref, value, round(px - e[0], 2), round(py - e[1], 2), nets, rot=rot, **kw)

    def _two_pin(self, lib_id, first, want):
        for rot in (0, 90, 180, 270):
            e = self.pin_ends(lib_id, 0, 0, rot)
            other = [k for k in e if k != first][0]
            dx, dy = e[other][0] - e[first][0], e[other][1] - e[first][1]
            if want == "down" and abs(dx) < 0.01 and dy > 0 or want == "right" and abs(dy) < 0.01 and dx > 0:
                return rot
        raise ValueError(lib_id)

    def vput(self, lib_id, ref, value, top, x, y, nets, **kw):
        """2-pin part standing vertically with pin `top` at (x, y)."""
        return self.put(lib_id, ref, value, top, x, y, nets, rot=self._two_pin(lib_id, top, "down"), **kw)

    def hput(self, lib_id, ref, value, left, x, y, nets, **kw):
        """2-pin part lying horizontally with pin `left` at (x, y)."""
        return self.put(lib_id, ref, value, left, x, y, nets, rot=self._two_pin(lib_id, left, "right"), **kw)

    def w(self, *pts):
        """Wire polyline through the given points."""
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            self.items.append('(wire (pts (xy %.2f %.2f) (xy %.2f %.2f)) (stroke (width 0) (type default)) (uuid "%s"))'
                              % (x1, y1, x2, y2, U()))

    def j(self, x, y):
        self.items.append('(junction (at %.2f %.2f) (diameter 0) (color 0 0 0 0) (uuid "%s"))' % (x, y, U()))

    def lab(self, net, x, y, d):
        """Net label at a wire end; d = direction the text runs: L, R, U, D."""
        self.label(net, x, y, {"R": 180, "L": 0, "U": 270, "D": 90}[d])

    def flag(self, net, x, y, wired=False):
        """PWR_FLAG with its pin at (x, y); wired=True: the pin sits on a wire (no label)."""
        self.pwr += 1
        self.part("power:PWR_FLAG", "#FLG%02d" % self.pwr, "PWR_FLAG", x, y, {"1": W if wired else net})

    def write(self, path):
        out = ['(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0") (uuid "%s") (paper "%s")'
               % (self.root, self.paper),
               '(title_block (title "%s") (date "%s") (rev "0") (company "Voron 2.4 350") (comment 1 "%s") (comment 2 "Generated by gen_schematic.py - edit the script, not this file"))'
               % (self.title, DATE, self.comment),
               '(lib_symbols %s)' % "\n".join(self.libs.values())]
        out += self.items
        out.append('(sheet_instances (path "/" (page "1"))))')
        txt = "\n".join(out)
        assert txt.count("(") == txt.count(")"), "unbalanced parentheses"
        open(path, "w").write(txt + "\n")
        pro = os.path.splitext(path)[0] + ".kicad_pro"
        if not os.path.exists(pro):
            open(pro, "w").write('{\n  "meta": {\n    "filename": "%s",\n    "version": 1\n  }\n}\n' % os.path.basename(pro))

# Footprints / parts
FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_R1206 = "Resistor_SMD:R_1206_3216Metric"
FP_R2512 = "Resistor_SMD:R_2512_6332Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_C1206 = "Capacitor_SMD:C_1206_3216Metric"
FP_C1210 = "Capacitor_SMD:C_1210_3225Metric"
FP_LED = "LED_SMD:LED_0603_1608Metric"
FP_TERM = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
FP_CLIP = "PowerMonitor:Fuseclip_Blade_Mini_Keystone_3557"  # one clip per designator, pair = 9.73 mm apart
FP_TP = "TestPoint:TestPoint_Pad_D1.5mm"
FP_MH = "MountingHole:MountingHole_3.2mm_M3"

SHUNT = {  # value -> (lcsc, mpn)
    "5m": ("C5375417", "Milliohm HoYLR2512-2W-5mR-1%"),  # 2 W, 1 % (Spider: 0.91 W at 1.35x 10 A fuse)
    "10m": ("C375688", "YAGEO PA2512FKE7W0R01E"),       # 2 W, 1 %, 50 ppm
    "20m": ("C7420049", "FOJAN FRM252WFR020TN"),        # 2 W, 1 %, 50 ppm (backup C2083112 YAGEO)
    "50m": ("C7420008", "FOJAN FRM252WFR050TN"),        # 2 W, 1 %, 50 ppm (backup C49164908 JIERR)
}

# Parts re-checked 2026-11-14 (stock + datasheet). (lcsc, mpn)
P = {
    "100n": ("C346191", "Samsung CL10B104KB8NFNC"),     # 100 nF 50 V X7R 0603 (C14663 out of stock)
    "2k2": ("C4190", "UNI-ROYAL 0603WAF2201T5E"),        # 2.2k 0603 1 %
    "1R": ("C22936", "UNI-ROYAL 0603WAF100KT5E"),        # 1 ohm 0603 1 %
    "120k": ("C25808", "UNI-ROYAL 0603WAF1203T5E"),      # 120k 0603 1 %
    "100k": ("C25803", "UNI-ROYAL 0603WAF1003T5E"),      # 100k 0603 1 %
    "100R": ("C22775", "UNI-ROYAL 0603WAF1000T5E"),      # 100 ohm 0603 1 %
    "49R9": ("C479116", "RESI PTFR1206B49R9P9"),         # 49.9 ohm 1206 0.1 % 25 ppm thin film
    "AO3400A": ("C20917", "AOS AO3400A"),
    "FLYBACK": ("C2480", "MDD SS14"),
    "F_COIL": ("C151135", "Littelfuse 0466001.NRHF"),    # 1 A fast, 63 V, 1206
}

def R(s, ref, val, x, y, a, b, lcsc="", mpn="", fp=FP_R0603, dnp=False, note=""):
    s.part("Device:R", ref, val, x, y, {"1": a, "2": b}, fp, lcsc, mpn, dnp, note)

def C(s, ref, val, x, y, a, b, lcsc="", mpn="", fp=FP_C0603, note=""):
    s.part("Device:C", ref, val, x, y, {"1": a, "2": b}, fp, lcsc, mpn, note=note)

def tvs_lib(name):
    try:
        kilib.raw_symbol("Diode", name)
        return "Diode:" + name
    except ValueError:
        # KiCad has no SMBJ symbols; Device:D_TVS is drawn bidirectional -> own unidirectional copy
        return "PowerMonitor:TVS_Uni" if name.endswith("A") and not name.endswith("CA") else "Device:D_TVS"

def tvs_uni_symbol():
    """Unidirectional TVS graphics from Diode:SMAJ24A (pin 1 = cathode, pin 2 = anode)."""
    b = kilib.flat_symbol("Diode", "SMAJ24A")
    b = b.replace('(symbol "Diode:SMAJ24A"', '(symbol "PowerMonitor:TVS_Uni"', 1)
    b = re.sub(r'\(symbol "(SMAJ24A|SM6T6V8A)_', '(symbol "TVS_Uni_', b)
    b = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "TVS_Uni"', b, 1)
    b = re.sub(r'\(property "Footprint" "[^"]*"', '(property "Footprint" ""', b, 1)
    b = re.sub(r'\(property "Description" "[^"]*"', '(property "Description" "Unidirectional TVS diode, pin 1 = cathode"', b, 1)
    return b

def tvs(s, name, ref, x, y, rail, lcsc, mpn, fp):
    lib_id = tvs_lib(name)
    p = s.pins(lib_id)
    names = {v[0]: k for k, v in p.items()}
    if "K" in names and "A" in names:
        nets = {names["K"]: rail, names["A"]: "GND"}
    else:
        nets = {"1": rail, "2": "GND"}
    s.part(lib_id, ref, name, x, y, nets, fp, lcsc, mpn)

# --------------------------------------------------------------------------
# Main board
# --------------------------------------------------------------------------
def tvs_v(s, name, ref, x, y, rail, lcsc, mpn, fp):
    """Unidirectional TVS standing vertically: cathode (rail) at (x, y), anode to GND below."""
    lib_id = tvs_lib(name)
    p = s.pins(lib_id)
    names = {v[0]: k for k, v in p.items()}
    top, bot = (names["K"], names["A"]) if "K" in names and "A" in names else ("1", "2")
    e = s.vput(lib_id, ref, name, top, x, y, {top: W, bot: W}, footprint=fp, lcsc=lcsc, mpn=mpn)
    return e[top], e[bot]

def gnd(s, x, y, length=2.54):
    """Short wire down from (x, y) ending in a GND label."""
    s.w((x, y), (x, y + length))
    s.lab("GND", x, y + length, "D")

def main_board():
    s = Sheet("main_board", "Power monitor - main board", "A1",
              "3x INA3221 (24 V / 5 V distribution) + STM32G071 mains V/I/W, I2C to the Pi")

    # ---- Block A: inputs, protection, flags -------------------------------
    X, Y = 25.4, 45.72
    s.text("INPUTS + PROTECTION", X, Y - 17.78)
    for k, (j, jname, rail, bus, tv, tlcsc, tmpn, jnote) in enumerate([
            ("J1", "24V IN", "24V_IN", "24V_BUS", "SMBJ24A", "C224017", "Littelfuse SMBJ24A",
             "24 V from LRS-200-24 (max ~8.5 A), 18 A terminal"),
            ("J2", "5V IN", "5V_IN", "5V_BUS", "SMBJ6.0A", "C113976", "MDD SMBJ6.0A",       # VRWM 6 V > 5.25 V Pi supply
             "5 V in (today: Spider 5 V; later dedicated PSU)")]):
        y = Y + k * 50.8
        e = s.put("Connector:Screw_Terminal_01x02", j, jname, "1", X + 7.62, y, {"1": W, "2": W}, rot=180,
                  footprint=FP_TERM, lcsc="C8465", mpn="Kangnex WJ500V-5.08-2P", note=jnote,
                  fields=((-5.08, -6.35, "center"), (-5.08, 3.81, "center")))
        s.w(e["2"], (X + 12.7, e["2"][1]))                 # pin 2 = GND (above pin 1 after rotation)
        s.lab("GND", X + 12.7, e["2"][1], "R")
        if k == 0:
            s.flag("GND", X + 10.16, e["2"][1], wired=True)
            s.j(X + 10.16, e["2"][1])
        s.w((X + 7.62, y), (X + 50.8, y))
        s.lab(rail, X + 50.8, y, "R")
        top, bot = tvs_v(s, tv, "D%d" % (k + 1), X + 22.86, y, rail, tlcsc, tmpn, "Diode_SMD:D_SMB")
        s.j(*top)
        gnd(s, *bot)
        s.flag(rail, X + 35.56, y, wired=True)
        s.j(X + 35.56, y)
        # bulk capacitance on the bus side of the input shunt
        yb = y + 22.86
        s.lab(bus, X + 15.24, yb, "L")
        caps = [("C14", "10u 50V", "C138687", "Samsung CL32B106KBJNNNE", FP_C1210),
                ("C15", "10u 50V", "C138687", "Samsung CL32B106KBJNNNE", FP_C1210)] if k == 0 else \
               [("C16", "10u", "C14860", "Samsung CL31B106KAHNNNE", FP_C1206)]
        xs = [X + 22.86 + i * 12.7 for i in range(len(caps))] + ([X + 22.86 + len(caps) * 12.7] if k == 1 else [])
        s.w((X + 15.24, yb), (xs[-1], yb))
        for i, (ref, val, lc, mp, fp) in enumerate(caps):
            e = s.vput("Device:C", ref, val, "1", xs[i], yb, {"1": W, "2": W}, footprint=fp, lcsc=lc, mpn=mp)
            if xs[i] != xs[-1]:
                s.j(xs[i], yb)
            gnd(s, *e["2"])
        if k == 1:
            s.flag(bus, xs[-1], yb, wired=True)

    # ---- Block B: INA3221 x3 with shunts + filters -------------------------
    # (chip, addr net, [(ch, hi, lo, shunt ref, value)])
    inas = [
        ("U1", "GND", [(1, "24V_IN", "24V_BUS", "RS1", "10m"),
                       (2, "24V_BUS", "SPIDER_F", "RS2", "5m"),
                       (3, "24V_BUS", "SB2040_F", "RS3", "20m")]),
        ("U2", "+3V3", [(1, "24V_BUS", "CHFAN_F", "RS4", "50m"),
                        (2, "24V_BUS", "NEVERMORE_F", "RS5", "50m"),
                        (3, "24V_BUS", "LIGHTS_F", "RS6", "20m")]),
        ("U3", "SDA", [(1, "24V_BUS", "SPARE_F", "RS7", "20m"),
                       (2, "5V_IN", "5V_BUS", "RS8", "10m"),
                       (3, "5V_BUS", "PI_F", "RS9", "20m")]),
    ]
    rnum, cnum = 1, 1
    for i, (u, a0, chans) in enumerate(inas):
        bx, by = 25.4 + i * 162.56, 152.4
        addr = {"GND": "0x40", "+3V3": "0x41", "SDA": "0x42"}[a0]
        s.text("%s INA3221 @ %s (A0 = %s)" % (u, addr, a0), bx, by - 7.62)
        for k, (ch, hi, lo, rs, val) in enumerate(chans):
            yp = by + 5.08 + k * 30.48        # IN+ line (shunt supply side)
            yn = yp + 7.62                    # IN- line (shunt load side)
            inp, inn = "%s_IN%dP" % (u, ch), "%s_IN%dN" % (u, ch)
            x0 = bx
            s.lab(inp, x0, yp, "L")
            s.lab(inn, x0, yn, "L")
            # differential filter cap between the two lines
            s.vput("Device:C", "C%d" % cnum, "100n 50V", "1", x0 + 7.62, yp, {"1": W, "2": W},
                   footprint=FP_C0603, lcsc=P["100n"][0], mpn=P["100n"][1], note="Differential input filter")
            s.j(x0 + 7.62, yp); s.j(x0 + 7.62, yn)
            # filter resistors (pin 2 = INA side)
            s.hput("Device:R", "R%d" % rnum, "1", "2", x0 + 15.24, yp, {"1": W, "2": W},
                   footprint=FP_R0603, lcsc=P["1R"][0], mpn=P["1R"][1], note="Input filter, Kelvin from shunt supply side")
            s.hput("Device:R", "R%d" % (rnum + 1), "1", "2", x0 + 15.24, yn, {"1": W, "2": W},
                   footprint=FP_R0603, lcsc=P["1R"][0], mpn=P["1R"][1], note="Input filter, Kelvin from shunt load side",
                   fields=((0, 2.54, "center"), (0, 5.08, "center")))
            s.w((x0, yp), (x0 + 15.24, yp)); s.w((x0, yn), (x0 + 15.24, yn))
            # shunt, Kelvin taps at its pads, power path continues to the right
            xs = x0 + 33.02
            lc, mp = SHUNT[val]
            s.vput("Device:R", rs, val, "1", xs, yp, {"1": W, "2": W}, footprint=FP_R2512, lcsc=lc, mpn=mp,
                   note="Current sense, Kelvin connection to the filter resistors")
            s.w((x0 + 22.86, yp), (xs + 15.24, yp)); s.w((x0 + 22.86, yn), (xs + 15.24, yn))
            s.j(xs, yp); s.j(xs, yn)
            s.lab(hi, xs + 15.24, yp, "R")
            s.lab(lo, xs + 15.24, yn, "R")
            rnum += 2
            cnum += 1
        # the INA itself
        cx, cy = bx + 104.14, by + 38.1
        nets = {"VS": W, "VPU": W, "GND": W, "EP": W, "A0": a0,
                "SCL": "SCL", "SDA": "SDA", "Warning": "WARNING", "Critical": "CRITICAL", "PV": None, "TC": None}
        for ch, hi, lo, rs, val in chans:
            nets["IN+%d" % ch] = "%s_IN%dP" % (u, ch)
            nets["IN-%d" % ch] = "%s_IN%dN" % (u, ch)
        e = s.part("PowerMonitor:INA3221", u, "INA3221AIRGVR", cx, cy, nets, lcsc="C181255", mpn="TI INA3221AIRGVR",
                   fields=((-12.7, -15.24, "left"), (2.54, -15.24, "left")))
        vs, vpu = e["4"], e["16"]
        s.w(vs, (vs[0] + 22.86, vs[1]))
        s.w(vpu, (vpu[0] + 5.08, vpu[1]), (vpu[0] + 5.08, vs[1]))
        s.j(vpu[0] + 5.08, vs[1])
        s.lab("+3V3", vs[0] + 22.86, vs[1], "R")
        ec = s.vput("Device:C", "C%d" % (10 + i), "100n", "1", vs[0] + 12.7, vs[1], {"1": W, "2": W},
                    footprint=FP_C0603, lcsc=P["100n"][0], mpn=P["100n"][1], note="INA VS decoupling, close to the pin")
        s.j(vs[0] + 12.7, vs[1])
        gnd(s, *ec["2"])
        g, ep = e["3"], e["17"]
        s.w(g, (g[0], g[1] + 2.54), (ep[0], g[1] + 2.54))
        s.w(ep, (ep[0], ep[1] + 5.08))
        s.j(ep[0], g[1] + 2.54)
        s.lab("GND", ep[0], ep[1] + 5.08, "D")

    # ---- Block C: fused outputs -------------------------------------------
    outs = [  # fuse ref, rating, from net, out net, conn ref, conn name, led R value
        ("F1", "10A", "SPIDER_F", "OUT_SPIDER", "J3", "SPIDER 24V", "10k"),
        ("F2", "5A", "SB2040_F", "OUT_SB2040", "J4", "SB2040 24V", "10k"),
        ("F3", "3A", "CHFAN_F", "OUT_CHFAN", "J5", "CHAMBER FANS 24V", "10k"),
        ("F4", "3A", "NEVERMORE_F", "OUT_NEVERMORE", "J6", "NEVERMORE 24V", "10k"),
        ("F5", "3A", "LIGHTS_F", "OUT_LIGHTS", "J7", "LIGHTS 24V", "10k"),
        ("F6", "3A", "SPARE_F", "OUT_SPARE", "J8", "SPARE 24V", "10k"),
        ("F7", "5A", "PI_F", "OUT_PI5V", "J9", "PI 5V", "1k"),
    ]
    bx, by = 25.4, 284.48
    s.text("FUSED OUTPUTS - mini blade (ATM) fuse in 2x Keystone 3557 clips; red LED lights when the fuse is blown "
           "and a load is connected", bx, by - 22.86)
    for i, (f, rating, src, dst, j, jname, rled) in enumerate(outs):
        x = bx + i * 68.58
        s.lab(src, x, by, "L")
        s.w((x, by), (x + 15.24, by))
        # Two clips per fuse, each its own designator (JLC places one part per designator).
        # Layout: place FxA/FxB 9.73 mm apart (centre to centre, legs in line) = ATM mini fuse.
        s.put("Connector_Generic:Conn_01x01", f + "A", "CLIP %s %s" % (f, rating), "1", x + 15.24, by, {"1": W},
              footprint=FP_CLIP, lcsc="C2680614", mpn="Keystone 3557", hide_val=True,
              note="Mini blade fuse clip, supply side. Fuse %s %s ATM" % (f, rating),
              fields=((0, -3.81, "center"), (0, 3.81, "center")))
        s.put("Connector_Generic:Conn_01x01", f + "B", "CLIP %s %s" % (f, rating), "1", x + 35.56, by, {"1": W},
              rot=180, footprint=FP_CLIP, lcsc="C2680614", mpn="Keystone 3557", hide_val=True,
              note="Mini blade fuse clip, load side. Fuse %s %s ATM" % (f, rating),
              fields=((0, -3.81, "center"), (0, 3.81, "center")))
        s.text("%s %s" % (f, rating), x + 21.59, by + 6.35, 1.5)
        s.w((x + 35.56, by), (x + 50.8, by))
        e = s.put("Connector:Screw_Terminal_01x02", j, jname, "1", x + 50.8, by, {"1": W, "2": W},
                  footprint=FP_TERM, lcsc="C8465", mpn="Kangnex WJ500V-5.08-2P",
                  fields=((2.54, -3.81, "left"), (2.54, 6.35, "left")))
        s.w(e["2"], (x + 48.26, e["2"][1]), (x + 48.26, by + 7.62))
        s.lab("GND", x + 48.26, by + 7.62, "D")
        # blown-fuse indicator: R + LED across the fuse
        yl = by - 10.16
        s.w((x + 7.62, by), (x + 7.62, yl), (x + 12.7, yl))
        s.j(x + 7.62, by)
        s.hput("Device:R", "RL%d" % (i + 1), rled, "1", x + 12.7, yl, {"1": W, "2": W},
               footprint=FP_R0603, lcsc="C25804" if rled == "10k" else "C21190",
               mpn="UNI-ROYAL 0603WAF1002T5E" if rled == "10k" else "UNI-ROYAL 0603WAF1001T5E")
        s.w((x + 20.32, yl), (x + 25.4, yl))
        s.hput("Device:LED", "LEDF%d" % (i + 1), "red", "2", x + 25.4, yl, {"1": W, "2": W},
               footprint=FP_LED, lcsc="C2286", mpn="KENTO KT-0603R", note="Fuse blown indicator")
        s.w((x + 33.02, yl), (x + 43.18, yl), (x + 43.18, by))
        s.j(x + 43.18, by)

    # ---- Block D: MCU + 3V3 ------------------------------------------------
    bx, by = 25.4, 355.6
    s.text("3V3 + STM32G071 (mains V/I/W, I2C target 0x50)", bx, by - 12.7)
    # LDO 5 V -> 3V3, then ferrite to the MCU supply
    e = s.part("Regulator_Linear:AP2112K-3.3", "U12", "AP2112K-3.3", bx + 33.02, by + 10.16,
               {"1": W, "2": W, "3": W, "5": W}, None, "C51118", "Diodes AP2112K-3.3TRG1",
               fields=((-7.62, -7.62, "left"), (-7.62, -5.08, "left")))
    vin, en, lg, vout = e["1"], e["3"], e["2"], e["5"]
    s.lab("5V_BUS", bx, vin[1], "L")
    s.w((bx, vin[1]), vin)
    s.w(en, (en[0] - 2.54, en[1]), (en[0] - 2.54, vin[1]))
    s.j(en[0] - 2.54, vin[1])
    ec = s.vput("Device:C", "C17", "1u", "1", bx + 10.16, vin[1], {"1": W, "2": W},
                footprint=FP_C0603, lcsc="C15849", mpn="Samsung CL10A105KB8NNNC", note="LDO input")
    s.j(bx + 10.16, vin[1]); gnd(s, *ec["2"], 5.08)
    gnd(s, *lg)
    yv = vout[1]
    s.w(vout, (bx + 60.96, yv))
    ec = s.vput("Device:C", "C13", "10u", "1", bx + 48.26, yv, {"1": W, "2": W},
                footprint=FP_C0805, lcsc="C15850", mpn="Samsung CL21A106KAYNNNE", note="LDO output / 3V3 bulk")
    s.j(bx + 48.26, yv); gnd(s, *ec["2"], 5.08)
    s.lab("+3V3", bx + 53.34, yv, "R")
    s.hput("Device:FerriteBead_Small", "FB1", "600R@100MHz", "1", bx + 60.96, yv, {"1": W, "2": W},
           footprint="Inductor_SMD:L_0603_1608Metric", lcsc="C85833", mpn="Murata BLM18KG601SN1D",
           note="Filters MCU/ADC supply (VDD=VDDA on LQFP-32)")
    s.w((bx + 66.04, yv), (bx + 109.22, yv))
    s.lab("+3V3_MCU", bx + 109.22, yv, "R")
    for k, (ref, val, lc, mp, fp, nt) in enumerate([
            ("C40", "4u7", "C1779", "Samsung CL21A475KAQNNNE", FP_C0805, ""),
            ("C41", "100n", P["100n"][0], P["100n"][1], FP_C0603, "Close to VDD pin 4"),
            ("C42", "1u", "C15849", "Samsung CL10A105KB8NNNC", FP_C0603, "")]):
        x = bx + 73.66 + k * 10.16
        ec = s.vput("Device:C", ref, val, "1", x, yv, {"1": W, "2": W}, footprint=fp, lcsc=lc, mpn=mp, note=nt)
        s.j(x, yv); gnd(s, *ec["2"], 5.08)
    s.flag("+3V3_MCU", bx + 104.14, yv, wired=True)
    s.j(bx + 104.14, yv)

    # MCU
    mx, my = bx + 165.1, by + 55.88
    mcu_nets = {
        "4": W, "5": W, "6": W,
        "7": "ADC_V", "8": "ADC_CT1", "15": "ADC_CT2", "16": "ADC_CT3", "14": "ADC_CT4",
        "11": "PA4_NSS", "10": "PA3_RX2", "21": "PA10_RX1", "32": "HEATER_EN_MCU",
        "30": "SCL", "31": "SDA", "18": "CRITICAL", "17": "LED_STAT",
        "24": "SWDIO", "25": "SWCLK",
    }
    e = s.part("PowerMonitor:STM32G071KBTx", "U10", "STM32G071KBT6", mx, my, mcu_nets,
               "Package_QFP:LQFP-32_7x7mm_P0.8mm", "C529348", "ST STM32G071KBT6",
               note="PA0=V, PA1/PB0/PB1/PA7=CT1-4 (all FT_a; PA5 is TT_a, no positive injection), PB6/PB7=I2C1 (= ROM bootloader I2C1, addr 0x51), PB8=heater relay enable",
               fields=((5.08, -33.02, "left"), (5.08, -30.48, "left")))
    vdd, vss, nrst = e["4"], e["5"], e["6"]
    s.w(vdd, (vdd[0], vdd[1] - 2.54))
    s.lab("+3V3_MCU", vdd[0], vdd[1] - 2.54, "U")
    gnd(s, *vss)
    # NRST: filter cap + reset button, to the left of the MCU
    xr = nrst[0] - 40.64
    s.w(nrst, (xr, nrst[1]))
    s.lab("NRST", nrst[0] - 7.62, nrst[1], "R")
    ec = s.vput("Device:C", "C43", "100n", "1", xr + 12.7, nrst[1], {"1": W, "2": W},
                footprint=FP_C0603, lcsc=P["100n"][0], mpn=P["100n"][1], note="NRST filter")
    s.j(xr + 12.7, nrst[1]); gnd(s, *ec["2"])
    ec = s.vput("Switch:SW_Push", "SW1", "RESET", "1", xr, nrst[1], {"1": W, "2": W},
                footprint="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", lcsc="C318884", mpn="XKB TS-1187A-B-A-B",
                fields=((-2.54, -1.27, "right"), (-2.54, 1.27, "right")))
    gnd(s, *ec["2"])
    # bootloader pin pull-ups (G07x bootloader V11.3 issue) + NSS idle high
    # AN2606 Rev 62 table 91: bootloader USART RX = PA10 (USART1), PA3 (USART2), PC11 (USART3, not
    # bonded on LQFP-32); SPI1 NSS = PA4. Pull them high so the bootloader only reacts to I2C1.
    xp = mx + 55.88
    s.text("Bootloader pins idle high (AN2606 Rev 62 table 91)", xp - 5.08, my - 33.02, 1.27)
    for i, net in enumerate(["PA3_RX2", "PA10_RX1", "PA4_NSS"]):
        x = xp + i * 12.7
        ec = s.vput("Device:R", "R%d" % (60 + i), "10k", "1", x, my - 25.4, {"1": "+3V3_MCU", "2": W},
                    footprint=FP_R0603, lcsc="C25804", mpn="UNI-ROYAL 0603WAF1002T5E",
                    note="Bootloader USART RX / SPI1 NSS idle high (AN2606 Rev 62 table 91)")
        s.w(ec["2"], (x, ec["2"][1] + 2.54))
        s.lab(net, x, ec["2"][1] + 2.54, "D")
    # status LED
    yl = my
    s.lab("LED_STAT", xp - 5.08, yl, "L")
    s.w((xp - 5.08, yl), (xp, yl))
    s.hput("Device:R", "R65", "1k", "1", xp, yl, {"1": W, "2": W}, footprint=FP_R0603, lcsc="C21190",
           mpn="UNI-ROYAL 0603WAF1001T5E")
    s.w((xp + 7.62, yl), (xp + 10.16, yl))
    s.hput("Device:LED", "LED10", "green", "2", xp + 10.16, yl, {"1": W, "2": W}, footprint=FP_LED,
           lcsc="C12624", mpn="KENTO KT-0603G", note="Status LED (active high)")
    s.w((xp + 17.78, yl), (xp + 22.86, yl))
    s.lab("GND", xp + 22.86, yl, "R")
    # BOOT0 recovery: PA14 (SWCLK) -> 10k -> solder jumper -> 3V3
    yb = my + 15.24
    s.lab("SWCLK", xp - 5.08, yb, "L")
    s.w((xp - 5.08, yb), (xp, yb))
    s.hput("Device:R", "R64", "10k", "1", xp, yb, {"1": W, "2": W}, footprint=FP_R0603, lcsc="C25804",
           mpn="UNI-ROYAL 0603WAF1002T5E", note="BOOT0 recovery (needs nBOOT_SEL = 0): PA14 is BOOT0 on G0")
    s.w((xp + 7.62, yb), (xp + 10.16, yb))
    s.hput("Jumper:SolderJumper_2_Open", "JP1", "BOOT0", "1", xp + 10.16, yb, {"1": W, "2": W},
           footprint="Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm", in_bom=False,
           note="Open by default. Works ONLY after nBOOT_SEL = 0 in the option bytes (factory = 1, BOOT0 pin ignored; AN2606 pattern 11)")
    s.w((xp + 17.78, yb), (xp + 22.86, yb))
    s.lab("+3V3_MCU", xp + 22.86, yb, "R")
    s.text("JP1 works only after nBOOT_SEL = 0 (factory 1)", xp - 5.08, yb + 6.35, 1.27)
    # SWD header
    s.part("Connector_Generic:Conn_01x05", "J22", "SWD", xp + 15.24, my + 38.1,
           {"1": "+3V3_MCU", "2": "SWDIO", "3": "SWCLK", "4": "NRST", "5": "GND"},
           "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical", in_bom=False,
           note="SWD: 3V3, SWDIO, SWCLK, NRST, GND (hand-soldered header)",
           fields=((2.54, -7.62, "left"), (2.54, 7.62, "left")))

    # ---- Block E: mains analog (CT signals + AC voltage) -------------------
    bx, by = 525.78, 45.72
    s.text("MAINS ANALOG - CT board via RJ45 (shielded Cat6) + AC-AC adapter", bx, by - 17.78)
    e = s.part("Connector:RJ45_Shielded", "J20", "RJ45 from CT board", bx, by + 10.16,
               {"1": "CT1_S", "2": "VBIAS", "3": "CT2_S", "6": "VBIAS", "4": "CT3_S", "5": "VBIAS",
                "7": "CT4_S", "8": "VBIAS", "SH": W},
               "PowerMonitor:RJ45_Kinghelm_KH-RJ45-58_Shielded_Horizontal", "C2683360", "kinghelm KH-RJ45-58-8P8C",
               note="Pairs: 1-2 CT1, 3-6 CT2, 4-5 CT3, 7-8 CT4. Shield tabs to GND here only",
               fields=((-7.62, -15.24, "left"), (-7.62, 25.4, "left")))
    gnd(s, *e["SH"])
    # shared 1.65 V bias
    xb = bx + 38.1
    s.vput("Device:R", "R70", "10k 0.1%", "1", xb, by - 7.62, {"1": "+3V3_MCU", "2": W},
           footprint=FP_R0603, lcsc="C95204", mpn="YAGEO RT0603BRD0710KL")
    ec = s.vput("Device:R", "R71", "10k 0.1%", "1", xb, by + 2.54, {"1": W, "2": W},
                footprint=FP_R0603, lcsc="C95204", mpn="YAGEO RT0603BRD0710KL")
    s.w((xb, by), (xb, by + 2.54))
    gnd(s, *ec["2"])
    s.w((xb, by + 2.54), (xb + 33.02, by + 2.54))
    s.j(xb, by + 2.54)
    s.lab("VBIAS", xb + 33.02, by + 2.54, "R")
    for k, (ref, val, lc, mp, fp) in enumerate([("C30", "10u", "C15850", "Samsung CL21A106KAYNNNE", FP_C0805),
                                                ("C31", "100n", P["100n"][0], P["100n"][1], FP_C0603)]):
        x = xb + 10.16 + k * 10.16
        ec = s.vput("Device:C", ref, val, "1", x, by + 2.54, {"1": W, "2": W}, footprint=fp, lcsc=lc, mpn=mp)
        s.j(x, by + 2.54); gnd(s, *ec["2"])
    # AC voltage input + divider
    e = s.part("Connector:Barrel_Jack", "J21", "AC 9V IN", bx, by + 63.5, {"1": W, "2": W},
               "Connector_BarrelJack:BarrelJack_Horizontal", "C2961147", "CUI PJ-002AH",
               note="9-12 V AC from a transformer-type AC-AC adapter (NOT DC). PJ-002AH matches this footprint (6.0 / 3.0 / 4.7 mm)",
               fields=((-5.08, -7.62, "left"), (-5.08, 7.62, "left")))
    ac, sl = e["1"], e["2"]
    s.w(sl, (sl[0] + 7.62, sl[1]))
    s.lab("VBIAS", sl[0] + 7.62, sl[1], "R")
    s.w(ac, (ac[0] + 7.62, ac[1]))
    s.hput("Device:R", "R72", "120k", "1", ac[0] + 7.62, ac[1], {"1": W, "2": W}, footprint=FP_R0603,
           lcsc=P["120k"][0], mpn=P["120k"][1],
           note="Divider /13: 9 V AC nominal -> 1.0 V peak, worst case (unloaded adapter, mains +10 %) 1.38 V peak")
    xn = ac[0] + 25.4
    s.w((ac[0] + 15.24, ac[1]), (xn + 10.16, ac[1]))
    s.lab("V_SENSE", xn + 10.16, ac[1], "R")
    ec = s.vput("Device:R", "R73", "10k 0.1%", "1", xn, ac[1], {"1": W, "2": W}, footprint=FP_R0603,
                lcsc="C95204", mpn="YAGEO RT0603BRD0710KL")
    s.j(xn, ac[1])
    s.w(ec["2"], (ec["2"][0], ec["2"][1] + 2.54))
    s.lab("VBIAS", ec["2"][0], ec["2"][1] + 2.54, "D")
    # per channel: (pull to VBIAS) + RC anti-alias + clamp
    chans = [("CT1_S", "ADC_CT1"), ("CT2_S", "ADC_CT2"), ("CT3_S", "ADC_CT3"), ("CT4_S", "ADC_CT4"), ("V_SENSE", "ADC_V")]
    rx = bx + 99.06
    for i, (src, adc) in enumerate(chans):
        y = by - 2.54 + i * 25.4
        s.lab(src, rx, y, "L")
        s.w((rx, y), (rx + 15.24, y))
        if i < 4:   # CT input defined when the RJ45 cable is unplugged (reads 0 A instead of floating)
            ec = s.vput("Device:R", "R%d" % (79 + i), "100k", "1", rx + 7.62, y, {"1": W, "2": W},
                        footprint=FP_R0603, lcsc=P["100k"][0], mpn=P["100k"][1],
                        note="Keeps the channel at VBIAS with the cable unplugged")
            s.j(rx + 7.62, y)
            s.w(ec["2"], (ec["2"][0], ec["2"][1] + 2.54))
            s.lab("VBIAS", ec["2"][0], ec["2"][1] + 2.54, "D")
        s.hput("Device:R", "R%d" % (74 + i), "2k2", "1", rx + 15.24, y, {"1": W, "2": W}, footprint=FP_R0603,
               lcsc=P["2k2"][0], mpn=P["2k2"][1], note="Anti-alias + fault current limit (< 3.1 mA into the clamp)")
        s.w((rx + 22.86, y), (rx + 50.8, y))
        s.lab(adc, rx + 50.8, y, "R")
        ec = s.vput("Device:C", "C%d" % (35 + i), "10n C0G", "1", rx + 27.94, y, {"1": W, "2": W},
                    footprint=FP_C0603, lcsc="C76599", mpn="TDK C1608C0G1H103JT000N", note="Anti-alias")
        s.j(rx + 27.94, y); gnd(s, *ec["2"])
        # BAV99: pin 1 = A1 (GND), 2 = K2 (3V3), 3 = K1/A2 (signal); KiCad 8 pin NAMES are wrong
        ec = s.put("Diode:BAV99", "D%d" % (10 + i), "BAV99", "3", rx + 40.64, y, {"1": W, "2": W, "3": W},
                   footprint=None, lcsc="C2500", mpn="Nexperia BAV99,215",
                   note="ADC clamp to rails. Pin 1 = A1 (GND), 2 = K2 (3V3), 3 = K1/A2 (signal); KiCad 8 pin NAMES are wrong, numbers are right",
                   fields=((0, -5.08, "center"), (0, -2.54, "center")))
        s.j(rx + 40.64, y)
        s.lab("GND", ec["1"][0], ec["1"][1], "L")
        s.lab("+3V3_MCU", ec["2"][0], ec["2"][1], "R")

    # ---- Block F: Pi header, alerts, I2C, test points ----------------------
    bx, by = 525.78, 205.74
    s.text("PI I2C HEADER + ALERTS", bx, by - 12.7)
    s.part("Connector_Generic:Conn_01x06", "J10", "TO PI", bx + 25.4, by + 7.62,
           {"1": "GND", "2": "SDA", "3": "SCL", "4": "CRITICAL", "5": "WARNING", "6": "HEATER_EN_PI"},
           "Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical", "C144397", "JST B6B-XH-A(LF)(SN)",
           note="Pi: GND pin 9, SDA GPIO2 pin 3, SCL GPIO3 pin 5, alerts + HEATER_EN_PI to free GPIOs (>= GPIO9: pulled low at boot)",
           fields=((2.54, -2.54, "left"), (2.54, 12.7, "left")))
    s.part("Connector_Generic:Conn_01x02", "J11", "TO SPIDER INPUT", bx + 25.4, by + 33.02,
           {"1": "CRITICAL", "2": "GND"}, "Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical", "C158012",
           "JST B2B-XH-A(LF)(SN)", note="Open-drain CRITICAL to a Spider endstop input (Klipper gcode_button)",
           fields=((2.54, -2.54, "left"), (2.54, 5.08, "left")))
    for k, (ref, val, net, lc, mp, dnp, nt) in enumerate([
            ("R19", "10k", "CRITICAL", "C25804", "UNI-ROYAL 0603WAF1002T5E", False, "Wired-OR pull-up"),
            ("R20", "10k", "WARNING", "C25804", "UNI-ROYAL 0603WAF1002T5E", False, "Wired-OR pull-up"),
            ("R21", "4k7", "SDA", "C23162", "UNI-ROYAL 0603WAF4701T5E", True, "DNP - the Pi has 1.8k pull-ups"),
            ("R22", "4k7", "SCL", "C23162", "UNI-ROYAL 0603WAF4701T5E", True, "DNP - the Pi has 1.8k pull-ups")]):
        x = bx + 55.88 + k * 12.7
        ec = s.vput("Device:R", ref, val, "1", x, by + 2.54, {"1": "+3V3", "2": W}, footprint=FP_R0603,
                    lcsc=lc, mpn=mp, dnp=dnp, note=nt)
        s.w(ec["2"], (x, ec["2"][1] + 2.54))
        s.lab(net, x, ec["2"][1] + 2.54, "D")
    tps = ["24V_IN", "24V_BUS", "5V_BUS", "+3V3", "+3V3_MCU", "VBIAS", "SDA", "SCL", "CRITICAL", "GND"]
    s.text("TEST POINTS + MOUNTING", bx + 116.84, by - 12.7, 1.5)
    for i, n in enumerate(tps):
        s.part("Connector:TestPoint", "TP%d" % (i + 1), n, bx + 121.92 + (i % 5) * 15.24, by + 7.62 + (i // 5) * 22.86,
               {"1": n}, FP_TP, fields=((0, -6.35, "center"), (0, -3.81, "center")), hide_val=True)
    for i in range(4):
        s.part("Mechanical:MountingHole", "H%d" % (i + 1), "M3", bx + 121.92 + i * 15.24, by + 58.42, {}, FP_MH,
               fields=((0, -3.81, "center"), (0, 3.81, "center")))

    # ---- Block G: heater safety relay driver --------------------------------
    # Coil is energised only while BOTH the STM32 (PB8) and the Pi (J10 pin 6) drive their
    # enable high: two low-side MOSFETs in series. Reset / boot / crash / unplugged = coil off.
    # The relay/contactor itself (NO contacts, cuts only the heater supply) sits off-board.
    bx, by = 525.78, 320.04
    s.text("HEATER SAFETY RELAY - coil on only if STM32 AND Pi enable (fail-safe, NO contacts)", bx, by - 12.7)
    xc = bx + 66.04                       # coil / MOSFET column
    yr = by + 10.16                       # RLY_V+ rail
    yc = by + 38.1                        # RLY_COIL- rail
    xf, xl, xd = bx + 15.24, bx + 30.48, bx + 45.72
    s.w((xf, by - 2.54), (xf, by))
    s.lab("24V_BUS", xf, by - 2.54, "U")
    s.vput("Device:Fuse", "F8", "1A", "1", xf, by, {"1": W, "2": W}, footprint="Fuse:Fuse_1206_3216Metric",
           lcsc=P["F_COIL"][0], mpn=P["F_COIL"][1], note="Coil supply fuse")
    s.w((xf, by + 7.62), (xf, yr), (xc - 5.08, yr), (xc - 5.08, yr + 12.7), (xc, yr + 12.7))
    s.lab("RLY_V+", xf + 2.54, yr, "R")
    # LED + R across the coil
    s.w((xl, yr), (xl, yr + 2.54)); s.j(xl, yr)
    s.vput("Device:R", "R87", "10k", "1", xl, yr + 2.54, {"1": W, "2": W}, footprint=FP_R0603, lcsc="C25804",
           mpn="UNI-ROYAL 0603WAF1002T5E")
    s.w((xl, yr + 10.16), (xl, yr + 12.7))
    s.vput("Device:LED", "LED11", "green", "2", xl, yr + 12.7, {"1": W, "2": W}, footprint=FP_LED,
           lcsc="C12624", mpn="KENTO KT-0603G", note="Relay energised")
    s.w((xl, yr + 20.32), (xl, yc), (xc, yc))
    # flyback diode across the coil (cathode to RLY_V+)
    s.w((xd, yr), (xd, yr + 7.62)); s.j(xd, yr)
    s.vput("Device:D", "D15", "SS14", "1", xd, yr + 7.62, {"1": W, "2": W}, footprint="Diode_SMD:D_SMA",
           lcsc=P["FLYBACK"][0], mpn=P["FLYBACK"][1], note="Flyback across the coil")
    s.w((xd, yr + 15.24), (xd, yc)); s.j(xd, yc)
    # coil terminal: pin 1 RLY_V+, pin 2 RLY_COIL-
    e = s.put("Connector:Screw_Terminal_01x02", "J12", "HEATER RELAY COIL", "1", xc, yr + 12.7, {"1": W, "2": W},
              footprint=FP_TERM, lcsc="C8465", mpn="Kangnex WJ500V-5.08-2P", note="24 V relay/contactor coil, <= 0.5 A",
              fields=((7.62, -2.54, "left"), (7.62, 0, "left")))
    s.w(e["2"], (xc, yc))
    s.lab("RLY_COIL-", xd + 2.54, yc, "R")
    # Q1 (STM32) on top of Q2 (Pi), both low side
    def fet(ref, note, ydrain, en_net, rg, rpd):
        q = s.put("Transistor_FET:AO3400A", ref, "AO3400A", "3", xc, ydrain, {"1": W, "2": W, "3": W},
                  footprint=None, lcsc=P["AO3400A"][0], mpn=P["AO3400A"][1], note=note,
                  fields=((2.54, -1.27, "left"), (2.54, 1.27, "left")))
        gx, gy = q["1"]
        s.hput("Device:R", rg, "100", "1", gx - 15.24, gy, {"1": W, "2": W}, footprint=FP_R0603,
               lcsc=P["100R"][0], mpn=P["100R"][1])
        s.lab(en_net, gx - 17.78, gy, "L")
        s.w((gx - 17.78, gy), (gx - 15.24, gy))
        s.w((gx - 7.62, gy), (gx, gy))
        ep = s.vput("Device:R", rpd, "100k", "1", gx - 5.08, gy, {"1": W, "2": W}, footprint=FP_R0603,
                    lcsc=P["100k"][0], mpn=P["100k"][1],
                    note="Off while the MCU is in reset" if ref == "Q1" else "Off with the Pi cable unplugged",
                    fields=((2.54, 2.54, "left"), (2.54, 5.08, "left")))
        s.j(gx - 5.08, gy)
        gnd(s, *ep["2"])
        return q
    s.w((xc, yc), (xc, yc + 5.08)); s.j(xc, yc)
    q1 = fet("Q1", "Enable from STM32 PB8", yc + 5.08, "HEATER_EN_MCU", "R83", "R84")
    s.w(q1["2"], (xc, q1["2"][1] + 5.08))
    s.lab("RLY_MID", xc, q1["2"][1] + 2.54, "R")
    q2 = fet("Q2", "Enable from the Pi (J10 pin 6)", q1["2"][1] + 5.08, "HEATER_EN_PI", "R85", "R86")
    gnd(s, *q2["2"])

    # ---- Design calculations on the sheet (full version: ../design_calcs.py) ---
    s.text("DESIGN CALCULATIONS - DC side (INA3221, datasheet SBOS576C)", 114.3, 27.94, 2.0)
    s.note([
        "Shunt full scale 163.84 mV, LSB 40 uV, offset 80 uV max.  P = I^2 x R.",
        "ATM fuse: 1.1x rating may flow indefinitely, 1.35x up to 30 min -> P@1.35xF is the worst case.",
        "CH                 Rsh   FS     LSB     Imax   P@Imax  P@1.1xF P@1.35xF Vos max",
        "U1.1 24V in        10m   16.4A  4.0mA   8.5A   0.72W   PSU OCP 11.9A: 1.42W  8.0mA",
        "U1.2 Spider         5m   32.8A  8.0mA   7.0A   0.24W   0.60W   0.91W    16mA",
        "U1.3 SB2040        20m    8.2A  2.0mA   3.5A   0.24W   0.60W   0.91W    4.0mA",
        "U2.1/2.2 fans/Nev  50m    3.3A  0.8mA   1.5A   0.11W   0.54W   0.82W    1.6mA",
        "U2.3/3.1 light/sp  20m    8.2A  2.0mA   2.0A   0.08W   0.22W   0.33W    4.0mA",
        "U3.2 5V in         10m   16.4A  4.0mA   4.0A   0.16W   -       -        8.0mA",
        "U3.3 Pi 5V         20m    8.2A  2.0mA   3.5A   0.24W   0.60W   0.91W    4.0mA",
        "-> all shunts 2512 2 W, <= 71 % worst case (Spider 10m would be 1.82 W -> 5m).",
        "",
        "Input filter R: IN- sinks 10 uA + Vbus/670k, IN+ only 10 uA -> extra 35.8 uA at 24 V.",
        "  10 ohm: 358 uV error = 36 mA on 10m (above the INA's own 80 uV)  -> rejected",
        "   1 ohm:  36 uV error = 3.6 mA on 10m (below INA offset spec)    -> R1-R18 = 1 ohm",
        "  1 ohm + 100 nF: fc = 1/(2 pi 2R C) = 796 kHz (TI: filter only >1 MHz transients)",
        "",
        "26 V abs max: SMBJ24A conducts from 26.7 V (VC 38.9 V) -> surge only. PSU MUST be 24.0 V.",
        "No reverse-polarity protection on J1/J2: reversed input kills U1-U3 (IN+- min -0.3 V).",
        "Alert pull-ups 10k: 0.33 mA sink (VOL 0.4 V @ 3 mA OK), rise 2.2 us @ 100 pF.",
        "Fuse LEDs: 24 V: (24-1.9)/10k = 2.2 mA, 49 mW;  5 V: (5-1.9)/1k = 3.1 mA, 10 mW (0603 = 100 mW).",
        "3V3 budget: 3x INA 1.35 + MCU 12 + LEDs/bias/pull-ups 2.1 = 15.5 mA of 600 mA, LDO 26 mW.",
        "Copper (IPC-2221, 2 oz outer, dT 10 C): 8.5 A 2.9 mm, 7 A 2.2 mm, 5 A 1.4 mm, 3 A 0.7 mm.",
    ], 114.3, 33.02)
    s.text("DESIGN CALCULATIONS - mains side + MCU", 693.42, 27.94, 2.0)
    s.note([
        "CT ZMCT103C 1000:1, burden 49.9 ohm (datasheet specs",
        "  0.2 %, <=15', 0-15 A linear at 50 ohm).",
        "  V = I/1000 x 49.9: 6.3 A -> 314 mV, 3.3 A -> 165 mV,",
        "  2.2 A -> 110 mV rms.  Swing +-1.60 V around 1.65 V",
        "  -> clips at 1.60/49.9 x 1000/sqrt2 = 22.7 A rms.",
        "  1 LSB = 3.3/4096/49.9 x 1000 = 16 mA (3.7 W);",
        "  RMS over 800 samples/200 ms -> < 1 mA resolution.",
        "  SMAJ5.0CA conducts at 6.4 V = 91 A rms -> fault only.",
        "AC adapter 9 V AC: worst 9 x 1.28 (unloaded) x 1.10",
        "  (mains +10 %) = 12.7 V rms = 17.9 V peak.",
        "  R72/R73 = 120k/10k (/13): 0.98 V nom, 1.38 V worst",
        "  peak (limit 1.60 V). 100k/10k gave 1.63 V = clipping.",
        "Adapter and CT loops return to VBIAS (J21 sleeve,",
        "  RJ45 pair), no current through R70/R71 -> no 50 Hz",
        "  ripple on VBIAS, no false power.",
        "Anti-alias 2.2k + 10 nF C0G: fc 7.2 kHz, 0.40 deg at",
        "  50 Hz (same on all channels -> cancels in V x I).",
        "  Fault (CT TVS 9.2 V around VBIAS): (1.65+9.2-3.3-0.8)",
        "  /2.2k = 3.1 mA into BAV99 (1k gave 6.75 mA). ADC pins",
        "  PA0/PA1/PA7/PB0/PB1 are FT_a: no positive injection,",
        "  -5 mA limit OK. PA5 (TT_a) not used.",
        "  100k CTx_S -> VBIAS: unplugged reads 0 A,",
        "  burden error 49.9/100k = 0.05 % (calibrated).",
        "",
        "I2C: 0x40/41/42 INA, 0x50 STM32 app, 0x51 ROM",
        "  bootloader (AN2606 Rev 62 tab 91: I2C1 PB6/PB7).",
        "  Bootloader USART RX PA10/PA3 + SPI1 NSS PA4 pulled",
        "  high; USART3 RX PC11 and SPI2 not on LQFP-32.",
        "  BOOT0 pin (JP1) is ignored until nBOOT_SEL = 0 is",
        "  written (factory 1, AN2606 pattern 11). Recovery",
        "  without it: SWD (J22, connect under reset).",
        "  Flash via i2c-gpio overlay (clock stretching).",
        "",
        "Heater relay: Q1 AND Q2 must be on. AO3400A",
        "  Vgs(th) <= 1.45 V -> fully on at 3.3 V.",
        "  Gate 100 ohm, 100k pull-down = off in reset/boot.",
        "  Coil <= 0.5 A: Q loss 0.5^2 x 2 x 0.05 = 25 mW.",
        "  LED: (24-1.9)/10k = 2.2 mA when energised.",
    ], 693.42, 33.02)

    s.write(os.path.join(HERE, "main_board.kicad_sch"))
    return s

# --------------------------------------------------------------------------
# CT board
# --------------------------------------------------------------------------
def ct_board():
    s = Sheet("ct_board", "Power monitor - CT board", "A4",
              "4x wire-through CTs. NO mains copper: mains wires only pass through the CT holes")
    s.text("CT BOARD - mains wires pass THROUGH the CT holes (double insulated, strain relieved)", 15.24, 25.4, 2.0)
    # 49.9 ohm: the burden the ZMCT103C accuracy / phase / linearity specs are given at
    cts = [("T1", "R1", "49.9", *P["49R9"], "CT1", "PRINTER TOTAL"),
           ("T2", "R2", "49.9", *P["49R9"], "CT2", "BED"),
           ("T3", "R3", "49.9", *P["49R9"], "CT3", "CHAMBER HEATER"),
           ("T4", "R4", "49.9", *P["49R9"], "CT4", "SPARE (future 48 V motor PSU)")]
    pairs = {"CT1": ("1", "2"), "CT2": ("3", "6"), "CT3": ("4", "5"), "CT4": ("7", "8")}
    for i, (t, r, val, lc, mp, ct, name) in enumerate(cts):
        x, y = 30.48 + i * 55.88, 76.2
        s.text(name, x - 10.16, y - 17.78, 1.5)
        e = s.part("PowerMonitor:ZMCT103C", t, "ZMCT103C", x, y, {"3": W, "4": W},
                   "PowerMonitor:ZMCT103C", "C94571", "ZHE MING LANG XI ZMCT103C",
                   note="Primary = mains wire through the dia 5 mm hole (no primary pins). Pad 3 = CT pin 1* (dot). All CTs same direction (P1* side = supply side)",
                   fields=((-5.08, -10.16, "left"), (-5.08, 10.16, "left")))
        (xs, ys), (xr, yr) = e["3"], e["4"]           # pin 3 (S) bottom, pin 4 (R) top
        s.w((xr, yr), (x + 38.1, yr)); s.w((xs, ys), (x + 38.1, ys))
        s.lab(ct + "_R", x + 38.1, yr, "R"); s.lab(ct + "_S", x + 38.1, ys, "R")
        # burden directly at the CT pins - secondary must never be open
        er = s.vput("Device:R", r, val, "2", x + 17.78, yr, {"1": W, "2": W}, footprint=FP_R1206, lcsc=lc, mpn=mp,
                    note="Burden directly at the CT pins - secondary must never be open")
        s.w(er["1"], (x + 17.78, ys))
        s.j(x + 17.78, yr); s.j(x + 17.78, ys)
        lib = "Diode:SMAJ5.0CA" if tvs_lib("SMAJ5.0CA") != "Device:D_TVS" else "Device:D_TVS"
        ed = s.vput(lib, "D%d" % (i + 1), "SMAJ5.0CA", "2", x + 27.94, yr, {"1": W, "2": W}, footprint="Diode_SMD:D_SMA",
                    lcsc="C320524", mpn="LGE SMAJ5.0CA", note="Bidirectional clamp across the burden")
        s.w(ed["1"], (x + 27.94, ys))
        s.j(x + 27.94, yr); s.j(x + 27.94, ys)
    p = {}
    for ct, (a, b) in pairs.items():
        p[a], p[b] = ct + "_S", ct + "_R"
    p["SH"] = None
    s.part("Connector:RJ45_Shielded", "J1", "RJ45 to main board", 251.46, 76.2, p,
           "PowerMonitor:RJ45_Kinghelm_KH-RJ45-58_Shielded_Horizontal", "C2683360", "kinghelm KH-RJ45-58-8P8C",
           note="Shield NOT connected on this board (grounded on the main board)")
    for i in range(4):
        s.part("Mechanical:MountingHole", "H%d" % (i + 1), "M3", 30.48 + i * 20.32, 160.02, {}, FP_MH)
    s.text("DESIGN CALCULATIONS", 110, 140, 2.0)
    s.note([
        "ZMCT103C: 5 A : 5 mA (1000:1), 4500 V isolation, linear 0-15 A,",
        "  accuracy 0.2 % / phase <= 15' specified at a 50 ohm burden -> 49.9 ohm 0.1 %.",
        "Signal V = I/1000 x 49.9 ohm: 1 A -> 50 mV rms, clips (+-1.6 V) at 22.7 A rms.",
        "Burden power at 15 A: (15 mA)^2 x 49.9 = 11 mW (1206 = 250 mW).",
        "SMAJ5.0CA: conducts from 6.4 V = 128 mA secondary = 91 A primary (fault only).",
        "Secondary is never open: burden sits at the CT pins, cable unplugged is safe.",
        "Hole dia 5 mm: one single conductor (L) with a thin extra sleeve, OD < 5 mm.",
    ], 110, 145)
    s.write(os.path.join(HERE, "ct_board.kicad_sch"))
    return s

if __name__ == "__main__":
    for b in (main_board(), ct_board()):
        print("wrote", b.project, "-", len(b.items), "items,", len(b.libs), "symbols")
    # stand-alone library with the custom symbol
    open(os.path.join(HERE, "PowerMonitor.kicad_sym"), "w").write(
        '(kicad_symbol_lib (version 20231120) (generator "gen_schematic.py")\n%s\n)\n'
        % ina_symbol().replace('(symbol "PowerMonitor:INA3221"', '(symbol "INA3221"', 1))
