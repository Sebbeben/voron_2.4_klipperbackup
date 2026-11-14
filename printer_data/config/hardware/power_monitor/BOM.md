# Power monitor / distribution board - BOM (rev 0, draft)

Written 2026-11-14. Status: DRAFT, not ordered. LCSC numbers other than the
INA3221 are not yet looked up - pick parts with the listed specs and add
the LCSC numbers before ordering (JLCPCB assembly uses them).

## Concept
- **Power distribution board with monitoring** for the electronics bay:
  24 V in -> measured -> internal bus -> 6 fused, individually measured
  outputs. Same for 5 V. Replaces the current distribution terminals.
- 3 x TI INA3221 = 9 channels, high side, on one I2C bus.
- 4 x PCB-mounted current transformers + mains voltage (via an AC-AC
  adapter) for the mains loads, sampled by an RP2350B on the board (section C).
- Read by the Raspberry Pi over I2C (`dtparam=i2c_arm=on` is already set):
  INA3221 at 0x40-0x42, RP2350B as I2C target at 0x50. Board 3.3 V from its
  own LDO (fed from the 5 V input).
- Sum check: 24 V input vs. sum of the 24 V outputs -> detects a fault on
  the board / measurement error.
- Mains is measured only through the isolated CTs - no 230 V copper on
  the board.

## Channel map (proposal - adjust before layout)
INA3221 shunt full scale 163.84 mV, LSB 40 uV.

| Chip / addr | Ch | Rail / load | Expected max | Fuse | Shunt | Full scale | LSB |
|---|---|---|---|---|---|---|---|
| U1 / 0x40 (A0=GND) | 1 | **24 V input** from LRS-200-24 | 8.5 A | - (PSU side) | 10 mOhm | 16.4 A | 4 mA |
| U1 | 2 | 24 V -> Spider (motors + logic + its fans) | 7 A | 10 A | 10 mOhm | 16.4 A | 4 mA |
| U1 | 3 | 24 V -> SB2040 (hotend + toolhead fans) | 3.5 A | 5 A | 20 mOhm | 8.2 A | 2 mA |
| U2 / 0x41 (A0=VS) | 1 | 24 V -> chamber heater fan(s) / bed fans | 1.5 A | 3 A | 50 mOhm | 3.3 A | 0.8 mA |
| U2 | 2 | 24 V -> Nevermore / exhaust | 1.5 A | 3 A | 50 mOhm | 3.3 A | 0.8 mA |
| U2 | 3 | 24 V -> lights (Daylight XXL) | 2 A | 3 A | 20 mOhm | 8.2 A | 2 mA |
| U3 / 0x42 (A0=SDA) | 1 | 24 V -> spare (12 V buck for the PTC fan, ...) | 2 A | 3 A | 20 mOhm | 8.2 A | 2 mA |
| U3 | 2 | **5 V input** | 4 A | - | 10 mOhm | 16.4 A | 4 mA |
| U3 | 3 | 5 V -> Pi (+ screen, USB cam via Pi) | 3.5 A | 5 A | 20 mOhm | 8.2 A | 2 mA |

Fan channels use 50 mOhm so a stalled or dead fan (current drop of
~0.1 A) is clearly visible.

### INA3221 26 V limit - mitigation
The INA3221 input common-mode range (and abs max) is 26 V, only ~2 V above
the 24 V rail. To keep margin:
- Set the LRS-200-24 output to 24.0 V (adjustable 21.6-28.8 V), check with
  a multimeter.
- The board sits on the PSU side; motor braking spikes are mostly absorbed
  by the Spider's own bulk capacitors.
- Input RC filter on every channel (10 Ohm + 100 nF), bulk capacitance and
  TVS on the 24 V bus. The TVS only catches large spikes (clamps > 26 V).
- If the rail ever needs to go above 24 V: INA238/INA228 (85 V), rev 1.

## A. Board components
| Ref | Qty | Part | Spec | Package | LCSC |
|---|---|---|---|---|---|
| U1-U3 | 3 | TI INA3221AIRGVR | 3-ch shunt/bus monitor, I2C, 0-26 V | QFN-16-EP 4x4 | C181255 |
| RS1, RS2, RS8 | 3 | Current sense resistor | 10 mOhm, 1 %, >= 2 W, TCR <= 100 ppm | 2512 | tbd |
| RS3, RS6, RS7, RS9 | 4 | Current sense resistor | 20 mOhm, 1 %, >= 1 W, TCR <= 100 ppm | 2512 | tbd |
| RS4, RS5 | 2 | Current sense resistor | 50 mOhm, 1 %, >= 1 W, TCR <= 100 ppm | 2512 | tbd |
| R1-R18 | 18 | Resistor (input filter, 2 per channel) | 10 Ohm, 1 % | 0603 | tbd |
| C1-C9 | 9 | Capacitor (input filter, differential) | 100 nF, 50 V, X7R | 0603 | tbd |
| C10-C12 | 3 | Capacitor (VS decoupling, 1 per chip) | 100 nF, 16 V, X7R | 0603 | tbd |
| C13 | 1 | Capacitor (3V3 bulk) | 10 uF, 16 V, X7R | 0805 | tbd |
| C14, C15 | 2 | Capacitor (24 V bus bulk) | 10 uF, 50 V, X7R | 1210 | tbd |
| C16 | 1 | Capacitor (5 V bus bulk) | 10 uF, 16 V, X7R | 1206 | tbd |
| D1 | 1 | TVS (24 V bus) | SMBJ24A, unidirectional | SMB | tbd |
| D2 | 1 | TVS (5 V bus) | SMBJ5.0A, unidirectional | SMB | tbd |
| R19, R20 | 2 | Pull-up for CRITICAL and WARNING (wired-OR over all 3 chips) | 10 kOhm | 0603 | tbd |
| R21, R22 | 2 | I2C pull-up - **DNP** (the Pi has 1.8 k on GPIO2/3) | 4.7 kOhm | 0603 | tbd |
| F1-F7 | 7 | PCB fuse holder, mini blade (ATM) | e.g. Keystone 3557-2 type, >= 15 A | THT | tbd |
| - | 7 | ATM fuses | 10 A x1, 5 A x2, 3 A x4 | - | - |
| LED1-LED7 | 7 | Fuse-blown indicator LED (across each fuse, with resistor) | red, 0603 + 24 V/5 V resistor | 0603 | tbd |
| J1 | 1 | 24 V input terminal | 2-pin 7.62 mm or 5.08 mm, >= 20 A | THT | tbd |
| J2 | 1 | 5 V input terminal | 2-pin 5.08 mm, >= 15 A | THT | tbd |
| J3-J9 | 7 | Output terminals (+ / GND) | 2-pin 5.08 mm, >= 15 A | THT | tbd |
| J10 | 1 | I2C/alert header to the Pi | JST-XH 6-pin: 3V3, GND, SDA, SCL, CRITICAL, WARNING | THT | tbd |
| TP | ~12 | Test points (bus V per channel, 3V3, SDA, SCL, GND) | - | - | - |
| H1-H4 | 4 | Mounting holes | M3 | - | - |

Address pins are hard-wired (no jumpers): U1 A0->GND (0x40), U2 A0->VS
(0x41), U3 A0->SDA (0x42). 0x43 (A0->SCL) stays free for a 4th chip.
PV and TC outputs: not used, left unconnected (open-drain).

### PCB
- 2 layers, **2 oz copper**, approx. 100 x 80 mm.
- 24 V bus and the input/Spider paths: wide pours on both layers with
  stitching vias (>= 10 A).
- **Kelvin connections** from the inner ends of each shunt pad, routed as a
  pair to the RC filter and the INA.
- Common GND plane; GND passes straight through (high-side sensing).
- Keep the INAs and I2C away from the high-current pours; exposed pads to GND.
- Silkscreen: channel names, fuse ratings, polarity, "24.0 V MAX".

## B. Cables / mounting
| Qty | Part | Note |
|---|---|---|
| 1 | 6-wire JST-XH cable to the Pi GPIO header | GND (pin 9), SDA GPIO2 (pin 3), SCL GPIO3 (pin 5), CRITICAL + WARNING to free GPIOs or a Spider input; 3V3 pin left unconnected (board has its own LDO, both sides 3.3 V logic) |
| - | Silicone wire 14 AWG (24 V input, Spider), 18 AWG (others) | |
| 1 | DIN-rail holder or printed mount for the electronics bay | |

## C. Mains: 4 x PCB-mounted current transformers + AC voltage, RP2350B
Replaces the PZEM modules. **No mains copper on the PCB**: the mains wire
is threaded through the hole of each CT; only the isolated secondary is
soldered to the board.

Why an MCU: a CT gives a 50 Hz AC signal. RMS needs fast sampling
(>= 2 kHz); the INA3221 cannot do that. The **RP2350B** (QFN-80 variant of
the RP2350) has 8 ADC inputs (GPIO40-47): 4 CTs + mains voltage + 3 spare.
It computes Vrms, Irms, real power (W), apparent power (VA), power factor,
energy (Wh) and mains frequency per channel, and acts as an **I2C target
(0x50) on the same bus** as the INA3221s, so the Pi reads everything over
one bus. (RP2040 has only 4 ADC inputs - not enough.)

**Mains voltage (230 V / 50 Hz) without mains on the PCB:** an external
AC-AC wall adapter (transformer type, 9-12 V **AC** output - not a DC
adapter) plugged into the same mains supply. Its low-voltage AC output is
divided down and biased to 1.65 V on the board (OpenEnergyMonitor emonTx
method). The adapter's transformer provides the isolation. Calibrate once
against a multimeter (the adapter's ratio is not exact). The ADC samples
are multiplexed, ~2 us apart per channel = < 0.1 degree phase error at
50 Hz, negligible for power factor.

| CT ch | Mains load | Expected max | Burden | Signal at max |
|---|---|---|---|---|
| CT1 | Printer total (mains in) | ~6 A | 100 Ohm | 0.60 V rms |
| CT2 | Bed heater (750 W) | 3.3 A | 150 Ohm | 0.50 V rms |
| CT3 | Chamber heater (<= 500 W, cold inrush higher) | 2.2 A | 150 Ohm | 0.33 V rms |
| CT4 | Spare (LRS-200 primary, Pi PSU, ...) | - | 150 Ohm | - |
| V | Mains voltage via 9 V AC adapter | 230 V +-10 % -> 9-12 V AC | 100 k / 10 k divider | ~1.0 V peak |

Signal biased at 1.65 V (mid-rail), peak <= 0.85 V -> stays within 0-3.3 V.

| Ref | Qty | Part | Spec | Package | LCSC |
|---|---|---|---|---|---|
| T1-T4 | 4 | Current transformer, PCB mount, **wire-through hole** | ZMCT103C type: 5 A : 5 mA (1000:1), >= 3 kV isolation, hole >= 5 mm | THT | tbd |
| R30-R33 | 4 | Burden resistor, right at the CT pins (CT secondary must never be open) | 100 / 150 Ohm, 0.1 %, 0.25 W | 1206 | tbd |
| D10-D13 | 4 | Clamp across each burden (protects ADC on inrush / fault) | BAV99 or TVS 3.3 V | SOT-23 | tbd |
| R34-R41 | 8 | Bias divider for 1.65 V (shared or per channel) | 10 kOhm, 1 % | 0603 | tbd |
| C30-C33 | 4 | Bias decoupling | 10 uF, X5R | 0805 | tbd |
| R42-R45, C34-C37 | 4+4 | Anti-alias RC to each ADC pin | 1 kOhm + 10 nF | 0603 | tbd |
| U10 | 1 | MCU | RP2350B (8 ADC inputs) | QFN-80 | tbd |
| J13 | 1 | AC adapter input | 2.1 mm barrel jack (AC, polarity irrelevant) | THT | tbd |
| R46, R47 | 2 | Voltage divider for the AC adapter | 100 kOhm + 10 kOhm, 0.1 % | 0603 | tbd |
| R48, R49, C38 | 2+1 | Bias 1.65 V for the voltage channel | 10 kOhm 1 % x2 + 10 uF | 0603/0805 | tbd |
| D14 | 1 | Clamp on the voltage ADC input | BAV99 | SOT-23 | tbd |
| - | 1 | External AC-AC adapter, 230 V -> 9 V AC, >= 500 mA | e.g. the type used with OpenEnergyMonitor (EU plug) | - | - |
| U11 | 1 | QSPI flash | W25Q16JVUXIQ (2 MB) or W25Q128 | USON-8 | tbd |
| Y1 | 1 | Crystal | 12 MHz, 15-20 pF load | 3225 | tbd |
| C40-C41 | 2 | Crystal load caps | per crystal datasheet (~15-27 pF) | 0603 | tbd |
| C42-C55 | ~14 | RP2350B decoupling (IOVDD, DVDD, ADC_AVDD, USB_OTP_VDD, VREG) + core regulator inductor | per RP2350 hardware design guide (100 nF / 4.7 uF / 3.3 uH) | 0603/0805 | tbd |
| U12 | 1 | LDO 5 V -> 3.3 V (board 3V3 for MCU + INAs, cleaner ADC) | AP2112K-3.3 or similar, >= 300 mA | SOT-23-5 | tbd |
| FB1 | 1 | Ferrite bead + 1 uF for ADC_AVDD | 600 Ohm @ 100 MHz | 0603 | tbd |
| SW1 | 1 | BOOTSEL button | tactile | SMD | tbd |
| J11 | 1 | USB-C (flashing / optional USB serial to the Pi) | 16-pin USB 2.0 + 2 x 5.1 k CC resistors, 27 Ohm series | SMD | tbd |
| J12 | 1 | SWD header | 3-pin 2.54 mm (SWDIO, SWCLK, GND) | THT | tbd |
| LED10 | 1 | Status LED + resistor | green | 0603 | tbd |

### CT layout and safety rules
- CTs on the board edge, mains wires pass through from outside and are
  strain-relieved (cable ties / printed clamp) so they cannot touch the
  low-voltage side.
- Use **double-insulated** mains wire through the CT (the CT's isolation
  rating assumes intact wire insulation).
- Burden resistor directly at the CT pins - an open CT secondary can
  produce high voltage.
- Keep a clear gap (no copper, or a routed slot) around the CT holes.
- 230 V wiring done by someone used to mains wiring.

## D. Software (to do)
- RP2350B firmware: sample 4 CT channels + voltage (~4 kHz each), over 10
  cycles (200 ms) compute Vrms, Irms, W, VA, PF, Hz, accumulate Wh; expose
  as I2C target 0x50.
- Python service on the Pi: reads the 3 INA3221 (0x40-0x42) and the RP2350B
  (0x50), publishes to Moonraker (MQTT sensor component) for history and
  Mainsail.
- Checks: 24 V input vs. sum of outputs; fan channel current too low ->
  warning; bed/chamber current while Klipper reports the heater off -> stuck
  SSR -> cut power via the Shelly relay.

## Open decisions
- Channel map above: which loads are actually wired separately today
  (check the electronics bay)? Is the Pi fed from its own 5 V PSU or a buck?
- CRITICAL alert: to a Klipper input (pause / shutdown) or only log?
- Mains voltage: decided 2026-11-14 - measured via AC-AC adapter (230 V / 50 Hz).
- RP2350B to the Pi: I2C target (current plan) or USB serial?
