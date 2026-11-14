#!/usr/bin/env python3
"""Generate the KiCad 8 schematics for the power monitor (main board + CT board).

All connections are made with net labels placed on the pin ends (no wires),
so the netlist is defined in one place below. Re-run after editing:
    python3 gen_schematic.py
Symbols come from the official KiCad 8.0.8 libraries in ./libsrc, plus a
custom INA3221 symbol defined here (not in the KiCad library).
"""
import os, re, sys, uuid
sys.dont_write_bytecode = True  # keep __pycache__ out of the config backup
import kilib

HERE = os.path.dirname(os.path.abspath(__file__))
DATE = "2026-11-14"

def U():
    return str(uuid.uuid4())

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
        self.root = U()
        self.libs = {}       # lib_id -> block
        self.items = []
        self.refs = set()
        self.pwr = 0

    def lib(self, lib_id):
        if lib_id not in self.libs:
            if lib_id == "PowerMonitor:INA3221":
                self.libs[lib_id] = ina_symbol()
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

    def part(self, lib_id, ref, value, x, y, nets, footprint=None, lcsc="", mpn="", dnp=False, note=""):
        """nets: {pin_number: net_name or None(=no-connect)}. Unlisted pins -> no-connect."""
        assert ref not in self.refs, ref
        self.refs.add(ref)
        block = self.lib(lib_id)
        if footprint is None:
            m = re.search(r'\(property "Footprint" "([^"]*)"', block)
            footprint = m.group(1) if m else ""
        pins = kilib.pins(block)
        hide = "(hide yes)"
        props = [
            ('Reference', ref, 2.54, -1.27, ""), ('Value', value, 2.54, 1.27, ""),
            ('Footprint', footprint, 0, 0, hide), ('Datasheet', "~", 0, 0, hide),
            ('Description', note, 0, 0, hide), ('LCSC', lcsc, 0, 0, hide), ('MPN', mpn, 0, 0, hide),
        ]
        if ref.startswith("#"):
            props = props[:2]
        ptxt = " ".join(
            '(property "%s" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27)) (justify left) %s))'
            % (k, v, x + dx, y + dy, h) for k, v, dx, dy, h in props)
        pin_txt = " ".join('(pin "%s" (uuid "%s"))' % (n, U()) for n in pins)
        self.items.append(
            '(symbol (lib_id "%s") (at %.2f %.2f 0) (unit 1) (exclude_from_sim no) (in_bom %s) (on_board yes) (dnp %s) (uuid "%s") %s %s '
            '(instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))'
            % (lib_id, x, y, "no" if ref.startswith("#") else "yes", "yes" if dnp else "no", U(), ptxt, pin_txt,
               self.project, self.root, ref))
        for num, (name, px, py, pa, etype) in pins.items():
            ax, ay = x + px, y - py
            net = nets.get(num, nets.get(name, "__NC__"))
            if etype == "no_connect":
                continue
            if net in (None, "__NC__"):
                self.nc(ax, ay)
            else:
                self.label(net, ax, ay, pa)

    def flag(self, net, x, y):
        self.pwr += 1
        self.part("power:PWR_FLAG", "#FLG%02d" % self.pwr, "PWR_FLAG", x, y, {"1": net})

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
FP_FUSE = "PowerMonitor:Fuseholder_Blade_Mini_Keystone_3557x2"  # 2 clips per fuse (3568 out of stock)
FP_TP = "TestPoint:TestPoint_Pad_D1.5mm"
FP_MH = "MountingHole:MountingHole_3.2mm_M3"

SHUNT = {  # value -> (lcsc, mpn)
    "10m": ("C375688", "YAGEO PA2512FKE7W0R01E"),       # 2 W, 1 %, 50 ppm
    "20m": ("C7420049", "FOJAN FRM252WFR020TN"),        # 2 W, 1 %, 50 ppm (backup C2083112 YAGEO)
    "50m": ("C7420008", "FOJAN FRM252WFR050TN"),        # 2 W, 1 %, 50 ppm (backup C49164908 JIERR)
}

# Parts re-checked 2026-11-14 (stock + datasheet). (lcsc, mpn)
P = {
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
        return "Device:D_TVS"

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
def main_board():
    s = Sheet("main_board", "Power monitor - main board", "A2",
              "3x INA3221 (24 V / 5 V distribution) + STM32G071 mains V/I/W, I2C to the Pi")

    # ---- Block A: inputs, protection, flags -------------------------------
    X, Y = 40.64, 38.1
    s.text("INPUTS + PROTECTION", X, Y - 15)
    s.part("Connector:Screw_Terminal_01x02", "J1", "24V IN", X, Y, {"1": "24V_IN", "2": "GND"},
           FP_TERM, "C8465", "Kangnex WJ500V-5.08-2P", note="24 V from LRS-200-24 (max ~8.5 A), 18 A terminal")
    s.part("Connector:Screw_Terminal_01x02", "J2", "5V IN", X, Y + 30.48, {"1": "5V_IN", "2": "GND"},
           FP_TERM, "C8465", "Kangnex WJ500V-5.08-2P", note="5 V in (today: Spider 5 V; later dedicated PSU)")
    tvs(s, "SMBJ24A", "D1", X + 38.1, Y, "24V_IN", "C224017", "Littelfuse SMBJ24A", "Diode_SMD:D_SMB")
    tvs(s, "SMBJ5.0A", "D2", X + 38.1, Y + 30.48, "5V_IN", "C110528", "Diodes SMBJ5.0A-13-F", "Diode_SMD:D_SMB")
    C(s, "C14", "10u 50V", X + 63.5, Y, "24V_BUS", "GND", "C138687", "Samsung CL32B106KBJNNNE", FP_C1210)
    C(s, "C15", "10u 50V", X + 76.2, Y, "24V_BUS", "GND", "C138687", "Samsung CL32B106KBJNNNE", FP_C1210)
    C(s, "C16", "10u", X + 63.5, Y + 30.48, "5V_BUS", "GND", "C14860", "Samsung CL31B106KAHNNNE", FP_C1206)
    s.flag("24V_IN", X + 95.25, Y)
    s.flag("5V_IN", X + 95.25, Y + 30.48)
    s.flag("GND", X + 107.95, Y)
    s.flag("+3V3_MCU", X + 107.95, Y + 30.48)

    # ---- Block B: INA3221 x3 with shunts + filters -------------------------
    # (chip, addr net, [(ch, hi, lo, shunt ref, value, out_net_after_fuse)])
    inas = [
        ("U1", "GND", [(1, "24V_IN", "24V_BUS", "RS1", "10m"),
                       (2, "24V_BUS", "SPIDER_F", "RS2", "10m"),
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
        bx, by = 25.4 + i * 152.4, 127.0
        addr = {"GND": "0x40", "+3V3": "0x41", "SDA": "0x42"}[a0]
        s.text("%s INA3221 @ %s (A0 = %s)" % (u, addr, a0), bx, by - 20)
        nets = {"VS": "+3V3", "VPU": "+3V3", "GND": "GND", "EP": "GND", "A0": a0,
                "SCL": "SCL", "SDA": "SDA", "Warning": "WARNING", "Critical": "CRITICAL",
                "PV": None, "TC": None}
        for ch, hi, lo, rs, val in chans:
            nets["IN+%d" % ch] = "%s_IN%dP" % (u, ch)
            nets["IN-%d" % ch] = "%s_IN%dN" % (u, ch)
        s.part("PowerMonitor:INA3221", u, "INA3221AIRGVR", bx + 101.6, by + 10.16, nets,
               lcsc="C181255", mpn="TI INA3221AIRGVR")
        C(s, "C%d" % (10 + i), "100n", bx + 139.7, by + 5.08, "+3V3", "GND", "C14663", "YAGEO CC0603KRX7R9BB104",
          note="INA VS decoupling, close to the pin")
        for k, (ch, hi, lo, rs, val) in enumerate(chans):
            cy = by + k * 33.02
            lc, mp = SHUNT[val]
            R(s, rs, val, bx, cy, hi, lo, lc, mp, FP_R2512,
              note="Current sense, Kelvin connection to the filter resistors")
            R(s, "R%d" % rnum, "1", bx + 15.24, cy, hi, "%s_IN%dP" % (u, ch), *P["1R"],
              note="Input filter, Kelvin from shunt supply side")
            R(s, "R%d" % (rnum + 1), "1", bx + 30.48, cy, lo, "%s_IN%dN" % (u, ch), *P["1R"],
              note="Input filter, Kelvin from shunt load side")
            C(s, "C%d" % cnum, "100n 50V", bx + 45.72, cy, "%s_IN%dP" % (u, ch), "%s_IN%dN" % (u, ch),
              "C14663", "YAGEO CC0603KRX7R9BB104", note="Differential input filter")
            rnum += 2
            cnum += 1

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
    bx, by = 25.4, 254.0
    s.text("FUSED OUTPUTS (LED lights when the fuse is blown and a load is connected)", bx, by - 20)
    for i, (f, rating, src, dst, j, jname, rled) in enumerate(outs):
        x = bx + i * 50.8
        s.part("Device:Fuse", f, rating, x, by, {"1": src, "2": dst}, FP_FUSE, "C2680614", "Keystone 3557 (x2 clips)",
               note="Mini blade (ATM) fuse in 2x Keystone 3557 clips, fuse %s" % rating)
        R(s, "RL%d" % (i + 1), rled, x + 12.7, by, src, "LEDF%d" % (i + 1), "C25804" if rled == "10k" else "C21190",
          "UNI-ROYAL 0603WAF1002T5E" if rled == "10k" else "UNI-ROYAL 0603WAF1001T5E")
        s.part("Device:LED", "LEDF%d" % (i + 1), "red", x + 12.7, by + 22.86, {"2": "LEDF%d" % (i + 1), "1": dst},
               FP_LED, "C2286", "KENTO KT-0603R", note="Fuse blown indicator")
        s.part("Connector:Screw_Terminal_01x02", j, jname, x + 40.64, by + 7.62, {"1": dst, "2": "GND"},
               FP_TERM, "C8465", "Kangnex WJ500V-5.08-2P")

    # ---- Block D: MCU + 3V3 ------------------------------------------------
    bx, by = 25.4, 330.2
    s.text("3V3 + STM32G071 (mains V/I/W, I2C target 0x50)", bx, by - 20)
    s.part("Regulator_Linear:AP2112K-3.3", "U12", "AP2112K-3.3", bx + 12.7, by,
           {"1": "5V_BUS", "2": "GND", "3": "5V_BUS", "5": "+3V3"}, None, "C51118", "Diodes AP2112K-3.3TRG1")
    C(s, "C17", "1u", bx, by + 20.32, "5V_BUS", "GND", "C15849", "Samsung CL10A105KB8NNNC", note="LDO input")
    C(s, "C13", "10u", bx + 25.4, by + 20.32, "+3V3", "GND", "C15850", "Samsung CL21A106KAYNNNE", FP_C0805, note="LDO output / 3V3 bulk")
    s.part("Device:FerriteBead_Small", "FB1", "600R@100MHz", bx + 45.72, by, {"1": "+3V3", "2": "+3V3_MCU"},
           "Inductor_SMD:L_0603_1608Metric", "C85833", "Murata BLM18KG601SN1D", note="Filters MCU/ADC supply (VDD=VDDA on LQFP-32)")
    C(s, "C40", "4u7", bx + 58.42, by + 20.32, "+3V3_MCU", "GND", "C1779", "Samsung CL21A475KAQNNNE", FP_C0805)
    C(s, "C41", "100n", bx + 71.12, by + 20.32, "+3V3_MCU", "GND", "C14663", "YAGEO CC0603KRX7R9BB104", note="Close to VDD pin 4")
    C(s, "C42", "1u", bx + 83.82, by + 20.32, "+3V3_MCU", "GND", "C15849", "Samsung CL10A105KB8NNNC")

    mcu_nets = {
        "4": "+3V3_MCU", "5": "GND", "6": "NRST",
        "7": "ADC_V", "8": "ADC_CT1", "15": "ADC_CT2", "16": "ADC_CT3", "12": "ADC_CT4",
        "11": "PA4_NSS", "10": "PA3_RX2", "21": "PA10_RX1", "32": "HEATER_EN_MCU",
        "30": "SCL", "31": "SDA", "18": "CRITICAL", "17": "LED_STAT",
        "24": "SWDIO", "25": "SWCLK",
    }
    s.part("PowerMonitor:STM32G071KBTx", "U10", "STM32G071KBT6", bx + 152.4, by + 15.24, mcu_nets,
           "Package_QFP:LQFP-32_7x7mm_P0.8mm", "C529348", "ST STM32G071KBT6",
           note="PA0=V, PA1/PB0/PB1/PA5=CT1-4, PB6/PB7=I2C1 (= ROM bootloader I2C1, addr 0x51), PB8=heater relay enable")
    # bootloader pin pull-ups (G07x bootloader V11.3 issue) + NSS idle high
    # AN2606 Rev 62 table 91: bootloader USART RX = PA10 (USART1), PA3 (USART2), PC11 (USART3, not
    # bonded on LQFP-32); SPI1 NSS = PA4. Pull them high so the bootloader only reacts to I2C1.
    for i, net in enumerate(["PA3_RX2", "PA10_RX1", "PA4_NSS"]):
        R(s, "R%d" % (60 + i), "10k", bx + 203.2 + i * 12.7, by, "+3V3_MCU", net, "C25804", "UNI-ROYAL 0603WAF1002T5E",
          note="Bootloader USART RX / SPI1 NSS idle high (AN2606 Rev 62 table 91)")
    C(s, "C43", "100n", bx + 203.2, by + 35.56, "NRST", "GND", "C14663", "YAGEO CC0603KRX7R9BB104", note="NRST filter")
    s.part("Switch:SW_Push", "SW1", "RESET", bx + 223.52, by + 35.56, {"1": "NRST", "2": "GND"},
           "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "C318884", "XKB TS-1187A-B-A-B")
    R(s, "R64", "10k", bx + 203.2, by + 63.5, "SWCLK", "BOOT0_JP", "C25804", "UNI-ROYAL 0603WAF1002T5E",
      note="BOOT0 recovery: PA14 is BOOT0 on G0")
    s.part("Jumper:SolderJumper_2_Open", "JP1", "BOOT0", bx + 223.52, by + 63.5, {"1": "BOOT0_JP", "2": "+3V3_MCU"},
           "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm", note="Open by default; bridge for ROM bootloader recovery")
    R(s, "R65", "1k", bx + 248.92, by, "LED_STAT", "LED_STAT_A", "C21190", "UNI-ROYAL 0603WAF1001T5E")
    s.part("Device:LED", "LED10", "green", bx + 248.92, by + 22.86, {"2": "LED_STAT_A", "1": "GND"},
           FP_LED, "C12624", "KENTO KT-0603G", note="Status LED (active high)")
    s.part("Connector_Generic:Conn_01x05", "J22", "SWD", bx + 279.4, by + 15.24,
           {"1": "+3V3_MCU", "2": "SWDIO", "3": "SWCLK", "4": "NRST", "5": "GND"},
           "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical", note="SWD: 3V3, SWDIO, SWCLK, NRST, GND")

    # ---- Block E: mains analog (CT signals + AC voltage) -------------------
    bx, by = 330.2, 38.1
    s.text("MAINS ANALOG - CT board via RJ45 (shielded Cat6) + AC-AC adapter", bx, by - 15)
    s.part("Connector:RJ45_Shielded", "J20", "RJ45 from CT board", bx, by + 12.7,
           {"1": "CT1_S", "2": "VBIAS", "3": "CT2_S", "6": "VBIAS", "4": "CT3_S", "5": "VBIAS",
            "7": "CT4_S", "8": "VBIAS", "SH": "GND"},
           "PowerMonitor:RJ45_Kinghelm_KH-RJ45-58_Shielded_Horizontal", "C2683360", "kinghelm KH-RJ45-58-8P8C",
           note="Pairs: 1-2 CT1, 3-6 CT2, 4-5 CT3, 7-8 CT4. Shield tabs to GND here only")
    # bias 1.65 V shared
    R(s, "R70", "10k 0.1%", bx + 30.48, by, "+3V3_MCU", "VBIAS", "C95204", "YAGEO RT0603BRD0710KL")
    R(s, "R71", "10k 0.1%", bx + 30.48, by + 22.86, "VBIAS", "GND", "C95204", "YAGEO RT0603BRD0710KL")
    C(s, "C30", "10u", bx + 43.18, by + 11.43, "VBIAS", "GND", "C15850", "Samsung CL21A106KAYNNNE", FP_C0805)
    C(s, "C31", "100n", bx + 55.88, by + 11.43, "VBIAS", "GND", "C14663", "YAGEO CC0603KRX7R9BB104")
    # AC voltage input
    s.part("Connector:Barrel_Jack", "J21", "AC 9V IN", bx, by + 63.5, {"1": "AC_A", "2": "VBIAS"},
           "Connector_BarrelJack:BarrelJack_Horizontal", "C2961147", "CUI PJ-002AH",
           note="9-12 V AC from a transformer-type AC-AC adapter (NOT DC). PJ-002AH matches this footprint (6.0 / 3.0 / 4.7 mm)")
    R(s, "R72", "120k", bx + 30.48, by + 63.5, "AC_A", "V_SENSE", *P["120k"],
      note="Divider /13: 9 V AC nominal -> 1.0 V peak, worst case (unloaded adapter, mains +10 %) 1.38 V peak")
    R(s, "R73", "10k 0.1%", bx + 30.48, by + 86.36, "V_SENSE", "VBIAS", "C95204", "YAGEO RT0603BRD0710KL")
    # CT input defined when the RJ45 cable is unplugged (reads 0 A instead of floating)
    for i in range(4):
        R(s, "R%d" % (79 + i), "100k", bx + 76.2 + i * 33.02, by + 12.7, "CT%d_S" % (i + 1), "VBIAS", *P["100k"],
          note="Keeps the channel at VBIAS with the cable unplugged")
    # per channel: RC anti-alias + clamp
    chans = [("CT1_S", "ADC_CT1"), ("CT2_S", "ADC_CT2"), ("CT3_S", "ADC_CT3"), ("CT4_S", "ADC_CT4"), ("V_SENSE", "ADC_V")]
    for i, (src, adc) in enumerate(chans):
        x = bx + 76.2 + i * 33.02
        R(s, "R%d" % (74 + i), "1k", x, by + 63.5, src, adc, "C21190", "UNI-ROYAL 0603WAF1001T5E", note="Anti-alias")
        C(s, "C%d" % (35 + i), "10n C0G", x + 12.7, by + 86.36, adc, "GND", "C76599", "TDK C1608C0G1H103JT000N", note="Anti-alias")
        s.part("Diode:BAV99", "D%d" % (10 + i), "BAV99", x + 6.35, by + 25.4, {"1": "+3V3_MCU", "2": "GND", "3": adc},
               None, "C2500", "Nexperia BAV99,215", note="ADC clamp to rails")

    # ---- Block F: Pi header, alerts, I2C, test points ----------------------
    bx, by = 330.2, 190.5
    s.text("PI I2C HEADER + ALERTS", bx, by - 15)
    s.part("Connector_Generic:Conn_01x06", "J10", "TO PI", bx, by + 7.62,
           {"1": "GND", "2": "SDA", "3": "SCL", "4": "CRITICAL", "5": "WARNING", "6": "HEATER_EN_PI"},
           "Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical", "C144397", "JST B6B-XH-A(LF)(SN)",
           note="Pi: GND pin 9, SDA GPIO2 pin 3, SCL GPIO3 pin 5, alerts + HEATER_EN_PI to free GPIOs (>= GPIO9: pulled low at boot)")
    s.part("Connector_Generic:Conn_01x02", "J11", "TO SPIDER INPUT", bx, by + 40.64,
           {"1": "CRITICAL", "2": "GND"}, "Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical", "C158012", "JST B2B-XH-A(LF)(SN)",
           note="Open-drain CRITICAL to a Spider endstop input (Klipper gcode_button)")
    R(s, "R19", "10k", bx + 30.48, by, "+3V3", "CRITICAL", "C25804", "UNI-ROYAL 0603WAF1002T5E", note="Wired-OR pull-up")
    R(s, "R20", "10k", bx + 43.18, by, "+3V3", "WARNING", "C25804", "UNI-ROYAL 0603WAF1002T5E", note="Wired-OR pull-up")
    R(s, "R21", "4k7", bx + 55.88, by, "+3V3", "SDA", "C23162", "UNI-ROYAL 0603WAF4701T5E", dnp=True,
      note="DNP - the Pi has 1.8k pull-ups")
    R(s, "R22", "4k7", bx + 68.58, by, "+3V3", "SCL", "C23162", "UNI-ROYAL 0603WAF4701T5E", dnp=True,
      note="DNP - the Pi has 1.8k pull-ups")
    tps = ["24V_IN", "24V_BUS", "5V_BUS", "+3V3", "+3V3_MCU", "VBIAS", "SDA", "SCL", "CRITICAL", "GND"]
    for i, n in enumerate(tps):
        s.part("Connector:TestPoint", "TP%d" % (i + 1), n, bx + 101.6 + (i % 5) * 15.24, by + 10.16 + (i // 5) * 25.4,
               {"1": n}, FP_TP)
    for i in range(4):
        s.part("Mechanical:MountingHole", "H%d" % (i + 1), "M3", bx + 101.6 + i * 15.24, by + 76.2, {}, FP_MH)

    # ---- Block G: heater safety relay driver --------------------------------
    # Coil is energised only while BOTH the STM32 (PB8) and the Pi (J10 pin 6) drive their
    # enable high: two low-side MOSFETs in series. Reset / boot / crash / unplugged = coil off.
    # The relay/contactor itself (NO contacts, cuts only the heater supply) sits off-board.
    bx, by = 330.2, 304.8
    s.text("HEATER SAFETY RELAY - coil on only if STM32 AND Pi enable (fail-safe, NO contacts)", bx, by - 15)
    s.part("Device:Fuse", "F8", "1A", bx, by, {"1": "24V_BUS", "2": "RLY_V+"}, "Fuse:Fuse_1206_3216Metric",
           *P["F_COIL"], note="Coil supply fuse")
    s.part("Connector:Screw_Terminal_01x02", "J12", "HEATER RELAY COIL", bx + 25.4, by + 2.54,
           {"1": "RLY_V+", "2": "RLY_COIL-"}, FP_TERM, "C8465", "Kangnex WJ500V-5.08-2P",
           note="24 V relay/contactor coil, <= 0.5 A")
    s.part("Device:D", "D15", "SS14", bx + 50.8, by, {"1": "RLY_V+", "2": "RLY_COIL-"}, "Diode_SMD:D_SMA",
           *P["FLYBACK"], note="Flyback across the coil")
    R(s, "R87", "10k", bx + 66.04, by, "RLY_V+", "LED_RLY_A", "C25804", "UNI-ROYAL 0603WAF1002T5E")
    s.part("Device:LED", "LED11", "green", bx + 66.04, by + 22.86, {"2": "LED_RLY_A", "1": "RLY_COIL-"},
           FP_LED, "C12624", "KENTO KT-0603G", note="Relay energised")
    s.part("Transistor_FET:AO3400A", "Q1", "AO3400A", bx + 25.4, by + 30.48,
           {"1": "Q1_G", "2": "RLY_MID", "3": "RLY_COIL-"}, None, *P["AO3400A"], note="Enable from STM32 PB8")
    s.part("Transistor_FET:AO3400A", "Q2", "AO3400A", bx + 25.4, by + 55.88,
           {"1": "Q2_G", "2": "GND", "3": "RLY_MID"}, None, *P["AO3400A"], note="Enable from the Pi (J10 pin 6)")
    R(s, "R83", "100", bx, by + 30.48, "HEATER_EN_MCU", "Q1_G", *P["100R"])
    R(s, "R84", "100k", bx + 7.62, by + 40.64, "Q1_G", "GND", *P["100k"], note="Off while the MCU is in reset")
    R(s, "R85", "100", bx, by + 55.88, "HEATER_EN_PI", "Q2_G", *P["100R"])
    R(s, "R86", "100k", bx + 7.62, by + 66.04, "Q2_G", "GND", *P["100k"], note="Off with the Pi cable unplugged")

    # ---- Design calculations on the sheet (full version: ../design_calcs.py) ---
    s.text("DESIGN CALCULATIONS - DC side (INA3221, datasheet SBOS576C)", 155, 22, 2.0)
    s.note([
        "Shunt full scale 163.84 mV, LSB 40 uV, offset 80 uV max.  P = I^2 x R, P@fuse = fuse rating^2 x R",
        "CH                 Rsh   FS     LSB     Imax   P@Imax  P@fuse  Vos max",
        "U1.1 24V in        10m   16.4A  4.0mA   8.5A   0.72W   -       8.0mA",
        "U1.2 Spider        10m   16.4A  4.0mA   7.0A   0.49W   1.00W   8.0mA",
        "U1.3 SB2040        20m    8.2A  2.0mA   3.5A   0.24W   0.50W   4.0mA",
        "U2.1/2.2 fans/Nev  50m    3.3A  0.8mA   1.5A   0.11W   0.45W   1.6mA",
        "U2.3/3.1 light/sp  20m    8.2A  2.0mA   2.0A   0.08W   0.18W   4.0mA",
        "U3.2 5V in         10m   16.4A  4.0mA   4.0A   0.16W   -       8.0mA",
        "U3.3 Pi 5V         20m    8.2A  2.0mA   3.5A   0.24W   0.50W   4.0mA",
        "-> all shunts 2512 >= 2 W (max load 50 %).",
        "",
        "Input filter R: IN- sinks 10 uA + Vbus/670k, IN+ only 10 uA -> extra 35.8 uA at 24 V.",
        "  10 ohm: 358 uV error = 36 mA on 10m (above the INA's own 80 uV)  -> rejected",
        "   1 ohm:  36 uV error = 3.6 mA on 10m (below INA offset spec)    -> R1-R18 = 1 ohm",
        "  1 ohm + 100 nF: fc = 1/(2 pi 2R C) = 796 kHz (TI: filter only >1 MHz transients)",
        "",
        "26 V abs max: SMBJ24A conducts from 26.7 V (VC 38.9 V) -> surge only. PSU MUST be 24.0 V.",
        "Alert pull-ups 10k: 0.33 mA sink (VOL 0.4 V @ 3 mA OK), rise 2.2 us @ 100 pF.",
        "Fuse LEDs: 24 V: (24-1.9)/10k = 2.2 mA, 49 mW;  5 V: (5-1.9)/1k = 3.1 mA, 10 mW (0603 = 100 mW).",
        "3V3 budget: 3x INA 1.35 + MCU 12 + LEDs/bias/pull-ups 2.1 = 15.5 mA of 600 mA, LDO 26 mW.",
        "Copper (IPC-2221, 2 oz outer, dT 10 C): 8.5 A 2.9 mm, 7 A 2.2 mm, 5 A 1.4 mm, 3 A 0.7 mm.",
    ], 155, 27)
    s.text("DESIGN CALCULATIONS - mains side + MCU", 505, 160, 2.0)
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
        "Anti-alias 1k + 10 nF C0G: fc 15.9 kHz, 0.18 deg at",
        "  50 Hz (same on all channels -> cancels in V x I).",
        "  Fault 9.2 V: (9.2-1.65-3.3-0.8)/1k = 3.4 mA into",
        "  BAV99 -> MCU pin < 5 mA OK.",
        "  100k CTx_S -> VBIAS: unplugged reads 0 A,",
        "  burden error 49.9/100k = 0.05 % (calibrated).",
        "",
        "I2C: 0x40/41/42 INA, 0x50 STM32 app, 0x51 ROM",
        "  bootloader (AN2606 Rev 62 tab 91: I2C1 PB6/PB7).",
        "  Bootloader USART RX PA10/PA3 + SPI1 NSS PA4 pulled",
        "  high; USART3 RX PC11 and SPI2 not on LQFP-32.",
        "  Flash via i2c-gpio overlay (clock stretching).",
        "",
        "Heater relay: Q1 AND Q2 must be on. AO3400A",
        "  Vgs(th) <= 1.45 V -> fully on at 3.3 V.",
        "  Gate 100 ohm, 100k pull-down = off in reset/boot.",
        "  Coil <= 0.5 A: Q loss 0.5^2 x 2 x 0.05 = 25 mW.",
        "  LED: (24-1.9)/10k = 2.2 mA when energised.",
    ], 505, 165)

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
        s.part("Device:Transformer_1P_1S", t, "ZMCT103C", x, y, {"1": None, "2": None, "3": ct + "_S", "4": ct + "_R"},
               "PowerMonitor:ZMCT103C", "C94571", "ZHE MING LANG XI ZMCT103C",
               note="Primary = mains wire through the dia 5 mm hole (pins 1-2 not connected). Pad 3 = CT pin 1* (dot). All CTs same direction (P1* side = supply side)")
        R(s, r, val, x + 20.32, y + 15.24, ct + "_S", ct + "_R", lc, mp, FP_R1206,
          note="Burden directly at the CT pins - secondary must never be open")
        s.part("Diode:SMAJ5.0CA" if tvs_lib("SMAJ5.0CA") != "Device:D_TVS" else "Device:D_TVS",
               "D%d" % (i + 1), "SMAJ5.0CA", x + 20.32, y + 35.56, {"1": ct + "_S", "2": ct + "_R"},
               "Diode_SMD:D_SMA", "C320524", "LGE SMAJ5.0CA", note="Bidirectional clamp across the burden")
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
