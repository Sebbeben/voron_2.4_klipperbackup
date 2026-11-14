# Power monitor / distribution board - BOM (rev 0, draft)

Written 2026-11-14. Status: DRAFT, not ordered. LCSC numbers other than the
INA3221 are not yet looked up - pick parts with the listed specs and add
the LCSC numbers before ordering (JLCPCB assembly uses them).

## Concept
- **Power distribution board with monitoring** for the electronics bay:
  24 V in -> measured -> internal bus -> 6 fused, individually measured
  outputs. Same for 5 V. Replaces the current distribution terminals.
- 3 x TI INA3221 = 9 channels, high side, on one I2C bus.
- Read directly by the Raspberry Pi over I2C (`dtparam=i2c_arm=on` is
  already set). No MCU. Logic powered from the Pi's 3.3 V.
- Sum check: 24 V input vs. sum of the 24 V outputs -> detects a fault on
  the board / measurement error.
- Mains (bed, chamber heater) is NOT on this board: separate, isolated
  PZEM-004T v3 modules with split-core CTs (section C).

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
| 1 | 6-wire JST-XH cable to the Pi GPIO header | 3V3 (pin 1), GND (pin 9), SDA GPIO2 (pin 3), SCL GPIO3 (pin 5), CRITICAL + WARNING to free GPIOs or a Spider input |
| - | Silicone wire 14 AWG (24 V input, Spider), 18 AWG (others) | |
| 1 | DIN-rail holder or printed mount for the electronics bay | |

## C. Mains measurement (separate, isolated modules - no DIY mains PCB)
| Qty | Part | Note |
|---|---|---|
| 2 | PZEM-004T v3.0, **100 A version with split-core CT** | V, A, W, kWh, PF. One for the bed, one for the chamber heater. Modbus-RTU over TTL, opto-isolated |
| 1 | USB-TTL adapter (CP2102 or CH340, 5 V TTL) | Both PZEMs on one bus with different Modbus addresses (set one at a time). The Pi UART is taken by the Spider |
| - | 230 V wiring for the PZEM voltage input | Fused, by someone used to mains wiring |

## D. Software (to do)
- Python service on the Pi: reads the 3 INA3221 (0x40-0x42) and the PZEMs
  (Modbus), publishes to Moonraker (MQTT sensor component) for history and
  Mainsail.
- Checks: 24 V input vs. sum of outputs; fan channel current too low ->
  warning; bed/chamber current while Klipper reports the heater off -> stuck
  SSR -> cut power via the Shelly relay.

## Open decisions
- Channel map above: which loads are actually wired separately today
  (check the electronics bay)? Is the Pi fed from its own 5 V PSU or a buck?
- CRITICAL alert: to a Klipper input (pause / shutdown) or only log?
- 3.3 V from the Pi (current plan) or an onboard LDO from 5 V?
