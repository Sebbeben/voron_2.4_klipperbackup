#!/usr/bin/env python3
"""Design calculations for the power monitor boards.

Run: python3 design_calcs.py > CALCULATIONS.txt
All datasheet values used are listed in DS below with their source, so the
numbers can be re-checked when a part changes.
"""
import math

DS = {
    # TI INA3221 datasheet SBOS576C (rev. Sept 2026), section 6.5 / 7.4.3
    "ina_vsh_fs": 163.84e-3,      # V, shunt full scale
    "ina_vsh_lsb": 40e-6,         # V
    "ina_vos_typ": 40e-6,         # V, shunt offset typ
    "ina_vos_max": 80e-6,         # V, shunt offset max
    "ina_iin_plus": 10e-6,        # A, IN+ bias
    "ina_iin_minus": 10e-6,       # A, IN- bias, plus Vbus / 670k
    "ina_rin_minus": 670e3,       # ohm
    "ina_vbus_abs": 26.0,         # V, abs max common mode
    "ina_iq_max": 450e-6,         # A
    "ina_vol_iol": (0.4, 3e-3),   # alert/SDA low level at 3 mA
    # Zeming ZMCT103C datasheet (LCSC C94571)
    "ct_ratio": 1000,
    "ct_burden_spec": 50.0,       # ohm, accuracy/phase/linearity specified here
    "ct_linear_max": 15.0,        # A rms, linear range at 50 ohm
    # STM32G071 ADC
    "adc_bits": 12,
    "vdda": 3.3,
    # Diodes SMBJ24A / SMBJ5.0A / SMAJ5.0CA (VBR min, VC max)
    "smbj24a": (26.7, 38.9),
    "smbj5a": (6.4, 9.2),
    "smaj5ca": (6.4, 9.2),
    # Diodes AP2112K
    "ap2112_iout": 0.6, "ap2112_vin_abs": 6.5,
}

def hdr(t):
    print("\n" + t + "\n" + "-" * len(t))

# ---------------------------------------------------------------------------
hdr("1. INA3221 channels: range, resolution, shunt power, offset")
VBUS24 = 24.0
chans = [  # name, shunt ohm, expected max A, fuse A (None = no fuse on board), vbus
    ("U1.1 24 V input", 0.010, 8.5, None, 24),
    ("U1.2 Spider", 0.010, 7.0, 10, 24),
    ("U1.3 SB2040", 0.020, 3.5, 5, 24),
    ("U2.1 chamber fans", 0.050, 1.5, 3, 24),
    ("U2.2 Nevermore", 0.050, 1.5, 3, 24),
    ("U2.3 lights", 0.020, 2.0, 3, 24),
    ("U3.1 spare 24 V", 0.020, 2.0, 3, 24),
    ("U3.2 5 V input", 0.010, 4.0, None, 5),
    ("U3.3 Pi 5 V", 0.020, 3.5, 5, 5),
]
print(f"{'channel':20s} {'Rsh':>6s} {'FS A':>6s} {'LSB mA':>7s} {'Pmax W':>7s} {'P@fuse W':>9s} {'Vos max mA':>10s}")
for name, r, imax, fuse, vb in chans:
    fs = DS["ina_vsh_fs"] / r
    lsb = DS["ina_vsh_lsb"] / r * 1e3
    p = imax ** 2 * r
    pf = (fuse ** 2 * r) if fuse else float("nan")
    vos = DS["ina_vos_max"] / r * 1e3
    print(f"{name:20s} {r*1e3:5.0f}m {fs:6.1f} {lsb:7.1f} {p:7.2f} {pf:9.2f} {vos:10.1f}")
print("All 2512 shunts must be rated >= 1 W (10 mOhm: >= 2 W, 1 W at 8.5 A is 72 % load).")
print("Note: a fuse lets ~1.35x its rating through for a long time, P@fuse is the real worst case.")

hdr("2. INA3221 input filter resistor error (IN- sinks Vbus/670k extra)")
for rf in (10.0, 1.0):
    for vb in (24.0, 5.0):
        di = vb / DS["ina_rin_minus"]           # extra IN- current vs IN+
        verr = di * rf
        print(f"Rfilt {rf:4.0f} ohm, Vbus {vb:4.0f} V: offset {verr*1e6:6.1f} uV "
              f"= {verr/0.010*1e3:5.1f} mA @10m, {verr/0.020*1e3:5.1f} mA @20m, {verr/0.050*1e3:5.1f} mA @50m")
for rf in (10.0, 1.0):
    fc = 1 / (2 * math.pi * 2 * rf * 100e-9)
    print(f"Rfilt {rf:4.0f} ohm + 100 nF differential: fc = {fc/1e3:6.0f} kHz")
print("-> 10 ohm gives up to 36 mA offset on the 10 mOhm channels (more than the INA's own")
print("   80 uV max). 1 ohm keeps it at 3.6 mA, below the INA offset spec, and still filters")
print("   the >1 MHz transients TI's 7.4.3 is about. Decision: R1-R18 = 1 ohm.")

hdr("3. 24 V bus vs INA3221 26 V abs max")
vbr, vc = DS["smbj24a"]
print(f"SMBJ24A starts conducting at {vbr} V (min) and clamps to {vc} V at peak current:")
print(f"it does NOT keep the INA below {DS['ina_vbus_abs']} V. It only stops big surges.")
print("-> PSU must be set to 24.0 V; braking spikes are absorbed by the Spider bulk caps.")
print("   If the bus ever needs headroom: INA238/INA228 (85 V).")

hdr("4. Open-drain alert pull-ups (R19, R20 = 10k to 3V3)")
i = 3.3 / 10e3
print(f"Sink current {i*1e3:.2f} mA per line (INA spec VOL 0.4 V at 3 mA) -> OK, 4 sinkers wired-OR.")
print(f"Rise time with ~100 pF cable: {2.2*10e3*100e-12*1e6:.1f} us -> fine for an alarm line.")

hdr("5. Fuse-blown LEDs (LED + R across each fuse; lights when the fuse is open AND a load is connected)")
for v, r in ((24, 10e3), (5, 1e3)):
    il = (v - 1.9) / r
    print(f"{v:2d} V rail, R {r/1e3:4.1f}k: LED {il*1e3:4.2f} mA, resistor {il*il*r*1e3:5.1f} mW (0603 = 100 mW)")
print("Leakage into a disconnected/off load with intact fuse: 0 (LED shorted by the fuse).")

hdr("6. 3V3 budget (AP2112K-3.3 from 5 V)")
loads = {"3x INA3221 (max)": 3 * DS["ina_iq_max"], "STM32G071 @64 MHz + ADC": 12e-3,
         "status LED": (3.3 - 2.0) / 1e3, "bias divider": 3.3 / 20e3, "alert pull-ups (both low)": 2 * 3.3 / 10e3}
tot = sum(loads.values())
for k, v in loads.items():
    print(f"  {k:28s} {v*1e3:6.2f} mA")
print(f"  total {tot*1e3:.1f} mA of {DS['ap2112_iout']*1e3:.0f} mA; LDO loss {(5-3.3)*tot*1e3:.0f} mW -> OK")
vbr5, vc5 = DS["smbj5a"]
print(f"5 V TVS SMBJ5.0A clamps at {vc5} V peak > AP2112 {DS['ap2112_vin_abs']} V abs max: surge-only protection,")
print("the 5 V source must be a regulated supply (it is).")

hdr("7. Current transformers (ZMCT103C, 1000:1)")
print(f"Datasheet accuracy, phase and linearity are given at {DS['ct_burden_spec']} ohm burden.")
print("Old design used 100/150 ohm (outside the spec). New: 49.9 ohm 0.1 % on all four.")
vhead = DS["vdda"] / 2 - 0.05            # usable peak swing around the 1.65 V bias
lsb = DS["vdda"] / 2 ** DS["adc_bits"]
for name, imax, rb in (("CT1 total", 6.3, 49.9), ("CT2 bed 750 W", 3.3, 49.9),
                       ("CT3 chamber 500 W", 2.2, 49.9), ("CT4 spare", 2.0, 49.9)):
    vrms = imax / DS["ct_ratio"] * rb
    iclip = vhead / rb * DS["ct_ratio"] / math.sqrt(2)
    print(f"{name:18s} {imax:4.1f} A -> {vrms*1e3:5.0f} mV rms, clips at {iclip:4.1f} A rms (sine), "
          f"1 LSB = {lsb/rb*DS['ct_ratio']*1e3:4.1f} mA = {lsb/rb*DS['ct_ratio']*230:4.1f} W")
n = 4000 // 50 * 10   # samples per 10-cycle window
print(f"RMS over {n} samples/window: quantisation noise ~LSB/sqrt(12*N) -> < 1 mA. Resolution is not the limit;")
print("CT accuracy (0.2 % class A / 0.4 % class E) and calibration are.")
vbr_t, vc_t = DS["smaj5ca"]
print(f"SMAJ5.0CA across the burden: conducts from {vbr_t} V = {vbr_t/49.9:.0f} mA secondary = "
      f"{vbr_t/49.9*1000/math.sqrt(2):.0f} A rms primary -> only faults/inrush.")

hdr("8. Mains voltage via 9 V AC adapter")
# Small 9 V AC transformer adapters run ~20-30 % high when unloaded; mains +10 %.
v_nom, v_worst = 9.0, 9.0 * 1.28 * 1.10
for rtop in (100e3, 120e3):
    ratio = (rtop + 10e3) / 10e3
    for v in (v_nom, v_worst):
        vp = v * math.sqrt(2) / ratio
        print(f"R72 {rtop/1e3:3.0f}k/10k (/{ratio:4.1f}): {v:5.2f} V rms -> {vp:4.2f} V peak at the ADC "
              f"(limit {vhead:.2f} V) {'OK' if vp < vhead*0.95 else 'TOO CLOSE'}")
print("-> R72 = 120k: 9 V nominal gives ~1.0 V peak, worst case ~1.38 V, 0.22 V margin.")
print("Adapter loop current ~0.1 mA flows adapter -> R72 -> R73 -> VBIAS -> adapter (J21 sleeve = VBIAS):")
print("it does not pass through the bias divider, so no 50 Hz ripple is injected into the CT channels.")
print("Same for the CTs: each pair returns to VBIAS, burden current stays on the CT board.")

hdr("9. ADC front end (1k + 10 nF C0G, BAV99 clamps)")
fc = 1 / (2 * math.pi * 1e3 * 10e-9)
ph = math.degrees(math.atan(2 * math.pi * 50 * 1e3 * 10e-9))
print(f"fc = {fc/1e3:.1f} kHz, phase at 50 Hz = {ph:.2f} deg (identical on all channels -> cancels in V*I)")
print(f"Charge sharing: 10 nF vs ~5 pF ADC sample cap -> {5e-12/10e-9*100:.2f} % kick, recovers via 1k in <1 us")
vf = (9.2 - 1.65 - 3.3 - 0.8) / 1e3
print(f"Fault: CT TVS at 9.2 V -> BAV99 clamp current through 1k = {vf*1e3:.1f} mA into +3V3_MCU (MCU pin < 5 mA) OK")
print("RJ45 unplugged: CTx_S would float -> add 100k CTx_S -> VBIAS on the main board (reads 0 A).")
print("  Load on the burden: 49.9 ohm || 100k = 0.05 % low -> calibrated out.")

hdr("10. Copper for the high-current paths (IPC-2221, external, 2 oz, dT 10 C)")
def width_mm(i, dt=10, oz=2):
    area_mil2 = (i / (0.048 * dt ** 0.44)) ** (1 / 0.725)
    return area_mil2 / (1.37 * oz) * 0.0254
for i in (8.5, 7.0, 5.0, 3.0):
    print(f"{i:4.1f} A -> {width_mm(i):4.1f} mm trace (or pour on both layers)")

hdr("11. I2C")
print("Pi pull-ups 1.8k on GPIO2/3 -> R21/R22 DNP. 4 targets: 0x40, 0x41, 0x42 (INA), 0x50 (STM32 app),")
print("0x51 (STM32 ROM bootloader, AN2606 Rev 62 table 91: I2C1 PB6/PB7, 0b1010001x). No collisions.")
print("The ROM bootloader stretches SCL during erase/write; the Pi's hardware I2C handles long clock")
print("stretching badly -> flash with the i2c-gpio overlay (bit-banged, supports stretching) at 100 kHz.")
print("App firmware: answer from buffered registers, no stretching (I2C NOSTRETCH).")
