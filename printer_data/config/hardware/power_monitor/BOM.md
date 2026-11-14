# Power monitor board - BOM (rev 0, draft)

Written 2026-11-14. Status: DRAFT, not ordered. LCSC numbers other than the
INA3221 are not yet looked up - pick parts with the listed specs and add
the LCSC numbers before ordering (JLCPCB assembly uses them).

## Concept
- 3-channel DC power monitor on the 24 V / 5 V side, TI INA3221 (high side).
- Read directly by the Raspberry Pi over I2C (`dtparam=i2c_arm=on` is
  already set). No MCU. Board powered from the Pi's 3.3 V.
- Mains (bed, chamber heater) is NOT measured on this board: separate,
  isolated PZEM-004T v3 modules with split-core CTs (section C).

| Ch | Rail | Expected max | Shunt | Full scale (163.84 mV) | LSB (40 uV) |
|---|---|---|---|---|---|
| 1 | 24 V total from LRS-200-24 | ~8.5 A (200 W) | 10 mOhm | 16.4 A | 4 mA |
| 2 | 24 V to SB2040 (hotend + fans) | ~3.5 A | 20 mOhm | 8.2 A | 2 mA |
| 3 | 5 V to the Pi | ~3 A | 20 mOhm | 8.2 A | 2 mA |

### INA3221 26 V limit - mitigation
The INA3221 input common-mode range (and abs max) is 26 V, only ~2 V above
the 24 V rail. To keep margin:
- Set the LRS-200-24 output to 24.0 V (it is adjustable 21.6-28.8 V) and
  check it with a multimeter.
- Measure on the PSU side of the rail, not after the stepper drivers
  (motor braking can pump the rail up locally).
- Input RC filter on every channel (10 Ohm + 100 nF) and bulk + TVS on the
  24 V rail. The TVS only catches large spikes (it clamps above 26 V).
- If the rail ever needs to go above 24 V: use INA238/INA228 (85 V) per
  channel instead (rev 1).

## A. Board components
| Ref | Qty | Part | Spec | Package | LCSC |
|---|---|---|---|---|---|
| U1 | 1 | TI INA3221AIRGVR | 3-ch shunt/bus monitor, I2C, 0-26 V | QFN-16-EP 4x4 | C181255 |
| R1 | 1 | Current sense resistor | 10 mOhm, 1 %, >= 2 W, low TCR (<= 100 ppm) | 2512 | tbd |
| R2, R3 | 2 | Current sense resistor | 20 mOhm, 1 %, >= 1 W, low TCR | 2512 | tbd |
| R4-R9 | 6 | Resistor (input filter) | 10 Ohm, 1 % | 0603 | tbd |
| C1-C3 | 3 | Capacitor (input filter, differential) | 100 nF, 50 V, X7R | 0603 | tbd |
| C4 | 1 | Capacitor (VS decoupling) | 100 nF, 16 V, X7R | 0603 | tbd |
| C5 | 1 | Capacitor (VS bulk) | 1 uF, 16 V, X7R | 0603 | tbd |
| C6, C7 | 2 | Capacitor (24 V bulk, ch1/ch2) | 10 uF, 50 V, X7R | 1210 | tbd |
| D1, D2 | 2 | TVS (24 V rails) | SMBJ24A, unidirectional | SMB | tbd |
| D3 | 1 | TVS (5 V rail) | SMBJ5.0A, unidirectional | SMB | tbd |
| R10-R13 | 4 | Pull-up (CRITICAL, WARNING, PV, TC alerts) | 10 kOhm | 0603 | tbd |
| R14, R15 | 2 | I2C pull-up - **DNP** (the Pi has 1.8 k on GPIO2/3) | 4.7 kOhm | 0603 | tbd |
| JP1 | 1 | Address select solder jumper (A0: GND/VS/SDA/SCL -> 0x40-0x43) | 4-way solder bridge | - | - |
| J1-J6 | 6 | Terminal block 2-pin (IN +/-, OUT +/- per channel) | 5.08 mm, >= 15 A, 300 V | THT | tbd |
| J7 | 1 | I2C/alert header to the Pi | JST-XH 6-pin: 3V3, GND, SDA, SCL, CRITICAL, WARNING | THT | tbd |
| TP1-TP6 | 6 | Test points (bus V per channel, 3V3, GND) | - | - | - |
| H1-H4 | 4 | Mounting holes | M3 | - | - |

### PCB
- 2 layers, **2 oz copper**, ~60 x 50 mm.
- Ch1 current path: >= 5 mm wide pours top + bottom with stitching vias.
- **Kelvin connections**: IN+/IN- traces from the inner ends of each shunt
  pad, routed as a pair to the filter and U1.
- Common GND plane (high-side sensing, GND passes straight through).
- Exposed pad of U1 to GND.
- Silkscreen: channel names, max current, polarity, "24.0 V MAX".

## B. Cables / mounting
| Qty | Part | Note |
|---|---|---|
| 1 | 6-wire JST-XH cable to the Pi GPIO header | 3V3 (pin 1), GND (pin 9), SDA GPIO2 (pin 3), SCL GPIO3 (pin 5), alerts to free GPIOs or a Spider input |
| - | Silicone wire 16 AWG (ch1), 18 AWG (ch2, ch3) | match existing wiring |
| 1 | DIN-rail holder or printed mount for the electronics bay | |

## C. Mains measurement (separate, isolated modules - no DIY mains PCB)
| Qty | Part | Note |
|---|---|---|
| 2 | PZEM-004T v3.0, **100 A version with split-core CT** | V, A, W, kWh, PF. One for the bed, one for the chamber heater. Modbus-RTU over TTL, opto-isolated |
| 1 | USB-TTL adapter (CP2102 or CH340, 5 V TTL) | Both PZEMs on one bus with different Modbus addresses (set one at a time). The Pi UART is taken by the Spider |
| - | 230 V wiring for the PZEM voltage input | Fused, by someone used to mains wiring |

## D. Software (to do)
- Python service on the Pi: reads INA3221 (I2C 0x40) and PZEMs (Modbus),
  publishes to Moonraker (MQTT sensor component) for history + Mainsail.
- Safety check: bed/chamber current > threshold while Klipper reports the
  heater off -> stuck SSR -> cut power via the Shelly relay.

## Open decisions
- Ch3: 5 V Pi rail, or 24 V to the Spider/motors instead?
- Alert outputs: wire CRITICAL to a Klipper input (pause / shutdown) or only log?
- 3.3 V from the Pi (current plan) or an onboard LDO from 5 V?
