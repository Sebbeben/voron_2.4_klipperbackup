# voron_2.4_klipperbackup

Klipper configuration backup for my Voron 2.4 350 (pushed automatically by [Klipper-backup](https://github.com/Staubgeborener/Klipper-Backup)).

## Hardware
- [Fysetc Voron 2.4 kit 350](https://github.com/FYSETC/FYSETC-Voron-2) (shipped with Spider v1.1 and Omron SSR, i.e. [BOM](https://github.com/FYSETC/FYSETC-Voron-2/blob/main/BOM.md) rev 1.3 / R2 rev 1.0)
  - XY + Z motors: 6x [17HS19-2004S-C](https://github.com/FYSETC/FYSETC-MOTORS/tree/main/17HS19-2004S-C) (2.0 A), run at 0.8 A
  - Bed heater: 300x300 silicone AC heater, 750 W, with thermal fuse RH15A125
- [Fysetc Aluminium parts kit](https://github.com/FYSETC/FYSETC-VORON-2.4-R2-Pro/tree/main/2.4%20R2%20CNC%20V2.0/2.4%20R2%20CNC%20V2.0)
- Raspberry Pi 4B 8GB
  - [Waveshare RS485 CAN HAT](https://www.waveshare.com/wiki/RS485_CAN_HAT) (MCP2515 over SPI, `oscillator=12000000, interrupt=25, spimaxfrequency=10000000` in `/boot/config.txt`)
- [Fysetc Spider v1.1](https://github.com/FYSETC/FYSETC-SPIDER) (connected to the Pi over UART `/dev/ttyAMA0`)
  - [Fysetc TMC2209 v3.1](https://github.com/FYSETC/FYSETC-TMC2209) ([Silent2209](https://fysetc.github.io/Silent2209/))
  - [Fysetc Canbus Expander for Spider](https://github.com/FYSETC/FYSETC-SPIDER/blob/main/images/CANBUS.jpg)
- [Mellow SB2040 v1](https://mellow-3d.github.io/fly_sb2040_v1_general.html#fly-sb2040-v1-overview) (CAN, 1 Mbit) - [pin definitions](https://mellow-3d.github.io/fly_sb2040_v1_pins.html)
- Orbiter extruder (version to be verified - `rotation_distance: 4.637` is the Orbiter 2.0 value)
  - [FYSETC G36HSY4405-6D-1200 stepper motor](https://github.com/FYSETC/FYSETC-MOTORS/blob/main/G36HSY4405-6D-1200/G36HSY4405-6D-1200.pdf), run at 0.65 A
- [Rapido UHF Hotend](https://www.phaetus.com/products/rapido-hotend?variant=45122834465045) (v1, HF + UHF nozzles included)
  - Currently: temporary V6 0.4 mm nozzle; plan: HF nozzle back, then UHF with a new toolhead
- [BTT Pi Screen 5"](https://github.com/bigtreetech/BIGTREETECH-TouchScreenHardware/tree/master/BTT%20Pi%20TFT50%20V2.0%20Github/Hardware)
- [BIQU CNC Voron Tap V2](https://github.com/Chaoticlab/CNC-Tap-for-Voron/tree/master/STL/CNC_VORON_TAP_V2) on SB2040 `gpio28` (replaced the Chaotic Labs Tap V2.0 / OptoTap v2.1). 2026-11-17: `PROBE_ACCURACY` stddev 0.0009 mm, range 0.0038 mm; `z_offset` -0.896
- X rail upgraded to MGN12H (needed for CNC Tap V2); Y and Z still original MGN9 (no grease ports). Greased with Mobilux EP 2
- CNC Aluminium Idlers
- [Meanwell LRS-200-24 psu](https://meanwell-ps.com/products/lrs-200-24)
- [Voron Daylight on a stick XXL](https://github.com/VoronDesign/Voron-Hardware/tree/master/Daylight) (`output_pin daylight`, PB15)
- Pi Cam (OV5647, 1280x720 @ 15 fps via Crowsnest)
- USB camera YJXU502S (Realtek RTS58xx, 0edc:2050), 1920x1080 @ 15 fps, Crowsnest `[cam 2]` ustreamer port 8081, Mainsail "USB Cam". The on-board LED is not controllable over USB (do not write to the UVC extension unit)
- Voron 2.4 silicone nozzle brush at the rear of the bed - KOMB area X 60.5-93.5, Y 347.5-350.0, Z 3.5 (Y 350.5 touches the frame)
- [Nevermore Duo](https://github.com/nevermore3d) under the bed (M3 T-nuts in the bed extrusion), 2 blowers in parallel on Spider FAN0 (`PB0`) as `[fan_generic nevermore]`. On in `PRINT_START` when bed > 90 C, off 10 min after `PRINT_END`
- ADXL345 accelerometer (loose, mounted on the toolhead only for calibration) wired to the Pi SPI0 bus, **CS on CE1 = pin 26 / GPIO7** (CE0 = pin 24 belongs to the MCP2515 CAN HAT - CS there kills CAN). Pi runs `klipper-mcu` as `[mcu rpi]`, `[adxl345] spi_bus: spidev0.1`, `axes_map: -z,-y,-x`
- Chamber air: 3 x NTC 100K (temporary test positions, Spider TE0/TE1/TE2 = PC0/PC1/PC2), `chamber_sensors.cfg`. Z `position_max` temporarily 200 while they hang under the top panel (restore 340)
- Gantry NTC (2026-11-25): a 4th NTC 100K pulled through the Z drag chain together with the new A/B motor cables, **not connected yet**. Plan: chamber air sensor on top of the gantry extrusion (moves with Z, so it reads the air at the gantry, which is what drives QGL/gantry drift). All Spider thermistor inputs are taken (PC0/PC1/PC2 chamber, PC3 bed), so it replaces one of the test sensors (`chamber_side` PC1 is the obvious one). Mounting: middle of the gantry, >= 100 mm from the A/B motors (they warm the aluminium), bead 10-20 mm above the extrusion in free air, not touching metal (printed standoff), outside the part-fan / Nevermore airflow. Expect it to read high at low Z (bed radiation) - only trust it for heatsoak at print height
- [OMRON G3NB-225B-1 25A SSR](https://www.omron-ap.com/products/family/3232/download/catalog.html)

### Fans
| Position | Fan | Pin | Status |
|---|---|---|---|
| Hotend (lower, 4010 axial) | [HoneyBadger 4010A-24-9400 "High SP & Tach"](https://3do.dk/en/fans/1145-4010-axial-fan-24v-by-honeybadger-high-sp-9400-rpm.html), 3-wire, not PWM | SB2040 fan adapter "Hotend Fan1": red -> 24V, black -> AGND (switched GND, `gpio14`); white tach **not connected** yet | **Installed 2026-11-17**, tested: on at 50 C, off below 50 C |
| Part cooling (upper, 5015 blower) | [HoneyBadger 5015 blower 9200 RPM, 4-wire PWM/tach, wide mouth](https://3do.dk/en/fans/4366-5015-blower-fan-by-honeybadger-9200-rpm-4-wires-pwmtach-wide-mouth.html) | SB2040 power `gpio13`, PWM `gpio17` | Ordered 2026-11-13 - duct needs adapting for the wide mouth |
| Electronics bay | Kit 6020 fans | Spider `PB2` (on when bed > 45 C) | Check that they still spin |
| Nevermore Duo | 2 x blower | Spider FAN0 `PB0` | Installed 2026-11-17 |

Hotend fan config: `printer.cfg` `[heater_fan hotend_fan]` (wiring in the comments). Stall watchdog: `hotend_fan_alarm.cfg` (included, idle until the tach is wired; plan 2026-11-25: tach -> SB2040 ENDSTOP_2 `gpio25`).

**Hotend fan wiring notes (learned the hard way, 2026-11-17):**
- On the Mellow fan adapter, "AGND" is the *switched* fan ground (low-side MOSFET), not analog ground. 2-wire / non-PWM fans go 24V + AGND.
- The adapter's "3 Line: S = PWM" row is for PWM fans only. A tach wire must **never** go to PWM0/PWM1: with the white tach on PWM0 (`gpio16`) the SB2040 MCU temperature read 120-135 C and Klipper shut down.
- The adapter has no tach input. SB2040 v1 inputs (schematic REV 1.0): ENDSTOP_0 `gpio28` (JP9, 4.7k pull-up to 3V3, Tap), ENDSTOP_1 `gpio29` (JP10, 4.7k pull-up, reserved for the X endstop), ENDSTOP_2 `gpio25` (JP11: 1 = signal, 2 = GND, 3 = **24 V**; input through a 1N4148 cathode-to-connector + 1k, 100 nF on the connector side, no pull-up -> 24 V tolerant, pulls low only). Status LED is `gpio24`, not 25.
- Tach plan: white wire -> JP11 pin 1, nothing on pin 3, `tachometer_pin: ^SB2040:gpio25`. First measure the white wire with the fan running and unconnected: if it shows a voltage the fan has its own pull-up and it works directly; if ~0 V add a 10k pull-up from the tach line to JP11 pin 3 (24 V), because the 100 nF + internal ~50k pull-up through the diode is too slow for ~310 Hz.

The part fan (5015) config is still prepared (commented out) in `fan_upgrade.cfg`.

## Hardware *Not installed*
- Mellow 3 m shielded twisted-pair CAN cable (20CANW3M) - plan: replace the current CAN cable
- FYSETC belt tension gauge (tool)
- Spare Orbiter motor: FYSETC 36STH20-1004AHG
- Simple filament runout switch
- Voron PT100 Stick
- Fysetc CNC Aluminium Clockwork extruder
- Unused kit parts: BMG extruder kit + 42HS20401B motor, E3D V6 hotend

## Klipper Mods
- [Klipper-backup](https://github.com/Staubgeborener/Klipper-Backup)
- [Klipper-Adaptive-Meshing-Purging (KAMP)](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging) - Smart_Park is used in `PRINT_START`
- [KOMB](https://github.com/TmRxJD/KOMB) nozzle brushing macro - **enabled 2026-11-17**. Local patch in `KOMB/KOMB.cfg`: travel to the brush at z_hop height *before* lowering (upstream lowers first and crosses the bed at brush height)
- [Filament dryer macro](https://gist.github.com/NameOfTheDragon/e579295549aaa19b3f41ae07b8f3cbd6#file-filament_dryer-cfg) - `DRY_ABS` = bed 95 C for 5 h (spool on a spacer, door slightly open)
- Crowsnest, Moonraker-timelapse, Sonar, KlipperScreen

## Printed Mods
- [Orbitu for Stealthburner Orbiter extruder](https://github.com/Saccco/VoronUsers/tree/master/printer_mods/Saccco/Orbitu)
- Planned: [Voron Stealthburner Rapido UHF](https://www.printables.com/model/1272320-voron-stealthburner-rapido-uhf) (4010 hotend fan version)

## Maintenance log

### 2026-11-18 - A/B motor fault hunt, motors ordered, camera sound in Mainsail
- Sensorless homing `uv_cp` fault traced step by step to **motor B** (supply, driver modules, X-MOT socket, both cables and endstop ports ruled out - details in TODO "A/B motor fault"). Motor A cable was also bad (open-load flags) and was replaced
- `homing_v2.cfg`: `G4 P2000` before sensorless `G28 X`/`G28 Y` (Klipper TMC docs); X/Y `homing_speed` back to 80
- Ordered 2 x LDO-42STH48-2504AC + 2 x adhesive heatsinks (3do.dk). Printer parked until they arrive; X-MOT/Y-MOT plugs and pins are temporarily swapped
- Driver/motor research: Spider v1.1 is 24 V only (35 V caps); TMC2240 (SPI, StallGuard4) is the next driver step; LDO "Super Power" 2804 only pays off with 48 V; no vibration dampers on A/B
- Chamber heater research (PTC 300-500 W, ~80 C practical limit, PA/PC possible, PEEK/PEI not) - TODO "Chamber heater"
- USB camera sound: go2rtc v1.9.14 installed as a service, nginx proxy `/go2rtc/`, Mainsail webcam "USB Cam + ljud" (WebRTC go2rtc, audio). Video via software x264 960x540 (the Pi hardware encoder only sent SPS/PPS once). Mic gain +12 dB (saved). Mainsail player patched (`printer_data/config/system/mainsail_go2rtc_audio_patch.sh`, re-run after Mainsail updates) - Mainsail kept re-muting the video and had no controls. Old MJPEG "USB Cam" entry removed. Sound verified on another PC (not yet on the main PC - local browser/PC issue)
- Camera LED: still no software control found (only Realtek raw-register XU 4, not touched). Connector has 5 pins - the extra pin is the next thing to check; seller asked

### 2026-11-17 - On site: homing, Tap, brush, Nevermore, input shaper, hotend fan
- `G28 X` shut down with `TMC stepper_x GSTAT uv_cp=1` (charge-pump undervoltage). Homing "finished" instantly (driver fault raises DIAG = fake stall). **Cause: loose 24 V cable** - re-tightened, homing fine since. If `uv_cp` comes back, check the 24 V terminals first.
- `homing_v2.cfg` enabled (fixed `SET_KINEMATIC_POSITION` defaulting to `SET_HOMED=xyz`), X/Y `homing_speed` 80 -> 40.
- CNC Tap V2: QGL converges in 2-3 retries, `PROBE_ACCURACY` stddev 0.0009 mm. `z_offset` -0.896 (paper test, cold nozzle, old value -0.810).
- KOMB brush measured and enabled (see Hardware).
- Nevermore Duo installed and configured.
- ADXL345 on the Pi + `klipper-mcu`; input shaper saved: **X `2hump_ei` 92 Hz, Y `mzv` 52.8 Hz**. X shows two broad peaks (~57 Hz and 115-135+ Hz, test stops at 135 Hz) -> toolhead not rigid yet (SB2040 only taped, ADXL ~16 deg tilted). Redo after the toolhead is finished with `SHAPER_CALIBRATE AXIS=X FREQ_END=170`. Graphs + raw data: `printer_data/config/shaper_graphs/` (rendered with `~/shaper-env`, a separate venv with matplotlib).
- Hotend fan HoneyBadger 4010 installed (see Fans), tach not wired yet.

### 2026-11-13 - Clog investigation
Symptom: clogs high up in the hotend, appearing "after a while", not at the same point every time.

Findings:
- **Root cause: the hotend fan was dead.** Cheap 2-wire sleeve-bearing 4010 (CAIZHU). 24 V measured at the fan with the port on, fan does not spin. Sleeve bearings wear out quickly in a ~60 C chamber, so the fan most likely slowed down over time, causing heat creep.
- Orbiter drive gears were packed with ground filament (extruder slipping against the blockage).
- Burnt ABS in the Rapido core and charred specks on the ceramic: leak between nozzle and heatbreak. Hot-tighten the nozzle at 250 C.
- Config history: `pressure_advance` was 0.3546 (10x too high) from 2025-06-17 to 2025-06-25. That week had ~15 failed prints and probably started the heatbreak contamination.
- Heatbreak cleaned with cold pulls; no clear evidence of scratches.
- Cura asks for up to ~22 mm3/s (p90) at 240 C with 300 mm/s infill, which is too much for this setup.

Config changes (backup of the old files kept locally):
- Extruder `run_current` 0.5 -> 0.65
- `PRINT_END` retract 5 mm -> 1.5 mm
- `UNLOAD_FILAMENT` now forms a tip before pulling out
- `DRY_ABS` bed 65 C / 4 h -> 95 C / 5 h
- Removed duplicate `sensor_type` in `[temperature_sensor RPi_4B]`
- Added `fan_upgrade.cfg` (inactive)

## TODO
- **Klipper local patch:** `klippy/mcu.py` TRSYNC_TIMEOUT 0.025 -> 0.050 (2026-11-26, Tap over CAN timed out during homing). Reapply after every Klipper update.
Status 2026-11-18: **printer parked** until new A/B motors arrive. Sensorless X/Y homing fails with TMC `uv_cp` (Undervoltage) - traced to the **motor B (stepper_x)**, see "A/B motor fault" below. Do not print until the motors are replaced.

### Done 2026-11-13
- [x] Klipper CPU pinning fixed (`[Service]` header) - Klipper runs on core 3
- [x] MCP2515 SPI clock 2 MHz -> 10 MHz in `/boot/config.txt` - after reboot: 0 `rx_over_errors` (was ~240-310/h at 2 MHz)
- [x] Software updated: Klipper v0.13.0-827, Moonraker v0.11, Mainsail v2.19, Crowsnest v4.2, klipper-backup, Sonar, KAMP (MCU firmware still v0.13.0-112/120 - works)
- [x] Adaptive mesh verified: already active via KAMP (`exclude_object` + Moonraker object processing)
- [x] KOMB include path fixed (still commented out), duplicate `KOMB.cfg` removed
- [x] Moonraker database backed up daily (03:30) by `moonraker-db-backup.timer` (systemd) via klipper-backup
- [x] OrcaSlicer profiles in `printer_data/config/orca_profiles/` (printer, process, ABS/ASA/PLA/PETG/TPU/PA/POM)
- [x] Prepared, not active: `homing_v2.cfg`, `load_unload_filament_v2.cfg`, `heatsoak.cfg`, `print_start_v2.cfg` (real soak, KAMP purge)
- [x] Firmware flashing plan: `printer_data/config/FLASHING.md`
- [x] Pi cam: camera-streamer hung at boot (no frames). Added crowsnest boot delay (`/etc/systemd/system/crowsnest.service.d/boot-delay.conf`), Mainsail webcam set to WebRTC 16:9

### Remote (Claude, no motion needed)
- [ ] Re-check CAN `rx_over_errors` after a long run / first print (should stay at 0)
- [ ] Import the Orca profiles on the PC and check them
- [ ] Verify the Pi cam works right after the next Pi reboot (crowsnest boot delay, see Done)
- [x] OS migration plan (Bullseye EOL -> MainsailOS v3 / Trixie on a new SD card): `printer_data/config/OS_MIGRATION.md`, system files in `printer_data/config/system/`

### A/B motor fault 2026-11-18 (printer parked)
Symptom: sensorless homing stops with `TMC 'stepper_x' reports error: GSTAT: 00000004 uv_cp=1(Undervoltage!)` (on 2026-11-17 also on stepper_y), false "homed" positions, erratic moves.

Ruled out with tests:
- 24 V supply: meter MIN/MAX on Spider PWR IN during failing homing 24.130-24.154 V (Spider v1.1 has no separate motor input)
- Driver modules: swapped X/Y modules with Z modules -> fault stayed on stepper_x
- Spider X-MOT socket: swapped the X-MOT/Y-MOT motor plugs + pins in the config -> fault followed motor B
- Motor B cable: new cable -> fault stayed
- Endstop ports X-/Y- are empty, PB13/PB14 used only as DIAG; normal moves, STEPPER_BUZZ and stealthChop moves are fine - the fault needs homing (stealthChop + StallGuard)
- Motor A cable was bad (open-load `ola/olb` flags during STEPPER_BUZZ, gone with a new cable)

Current state (temporary!):
- X-MOT/Y-MOT motor plugs are **swapped** and `printer.cfg` has the matching swapped pins (`# SOCKET SWAP TEST` comments). Restore both together (backup `~/clog_fix_backup_20261113/printer.cfg.before_socketswap_20261118`)
- `homing_v2.cfg`: `G4 P2000` before `G28 X`/`G28 Y` (Klipper TMC docs), X/Y `homing_speed` 80
- Z `position_max` 200 (chamber NTCs), gantry around Z 140

Plan:
- [x] Ordered 2026-11-18 from 3do.dk: 2 x LDO-42STH48-2504AC (1.8 deg, 2.5 A, ~1.2 ohm, ~1.5 mH) + 2 x NEMA17 adhesive heatsink
- [ ] Fit both motors as A and B with **new cables on both**, heatsinks on the back (clean with IPA). No vibration dampers on A/B
- [ ] Restore the motor plugs (B -> X-MOT, A -> Y-MOT) and the original stepper_x/y pins
- [ ] `run_current: 1.2` on the TMC2209 (watch `otpw`, max ~1.4-1.6 A with good electronics bay cooling)
- [ ] Keep sensorless homing: recalibrate `driver_SGTHRS` and the home current (0.49 A) for the new motors
- [ ] Re-run input shaper (re-enable klipper-mcu + `[mcu rpi]`/`[adxl345]`), X with `FREQ_END=170`
- [ ] Restore Z `position_max` 340 when the chamber NTCs are moved
- [x] Belt tension by sound: `printer_data/config/tools/belt_freq.py` (2026-11-25). Records the camera mic (ALSA, or go2rtc RTSP `usbcam_audio` when the mic is busy), finds each pluck and prints the fundamental (FFT 60-250 Hz) per pluck + median. Run macro `BELT_FREQ [SECONDS=8]` (Mainsail / KlipperScreen Macros, result in the console; `tools/belt_freq.cfg` + KIAUH `gcode_shell_command.py` in klippy/extras, git-excluded) or `python3 ~/printer_data/config/tools/belt_freq.py --seconds 8`, pluck 3-6 times. **KlipperScreen panel** (More -> Belt tension): Start/Stop, live frequency per pluck, median, Save A / Save B with A-B difference; `tools/ks_belt_freq.py` symlinked to `~/KlipperScreen/panels/belt_freq.py` (git-excluded), menu entry at the top of `KlipperScreen.conf`. Re-create the symlink if KlipperScreen is re-cloned. Tested with synthetic plucks (110.2 Hz); real belts after the motor swap. Ambient peak ~82 Hz from the fans - turn them off while measuring
- [ ] Later: 2 x BTT TMC2240 (SPI, StallGuard4 so sensorless homing keeps working) for X/Y -> 2504AC at ~1.6-1.8 A. Check the BTT module pinout against the Spider v1.1 SPI jumpers first
- Spider v1.1 is 24 V only (100 uF 35 V caps at the drivers). 48 V or LDO "Super Power" 2804 motors need a new board or external drivers

### Chamber heater
- [ ] PTC heater with fan for PA/PC (chamber 60-80 C): ~300-500 W, SSR + `[heater_generic chamber]`, `max_temp` ~70-80, fan interlocked, thermal fuse in series, mount in PA-CF/GF. Measure the bed-only chamber heat loss first (bed 110 C, 60-90 min) to size it. Practical limit for this Voron ~80 C (motors, belts, rail grease); PEEK/PEI/PEKK are out of reach
- [ ] Insulate panels/floor first (cheap, +5-10 C)
- Candidate: PTCYIDU (Shanghai Yidu) insulated PTC air heater JQ-96A2-220V-500W-CK, 140x50.5x26 mm, 230 V 500 W (inrush ~1000 W / 4 A), PA66 end brackets, built-in auto-reset bimetal on the side (opens 150 C, recloses 130 C), chip Ts 260 C
  - Fin surface: ~230 C with NO airflow, 80-120 C with fan (vendor, 2026-11-23)
  - **Insulation not trusted:** datasheet withstand voltage only 400 V; vendor cannot guarantee 1500 V AC/1 min, >=100 MOhm @500 V DC or <=0.75 mA leakage; no PE point on the aluminium (custom option). CE/RoHS + UL test report available on request
  - [ ] **Ground it ourselves:** clamp (stainless clip/hose clamp) on the outer aluminium edge, oxide scraped, serrated washer, crimped ring lug, green/yellow >= 0.75 mm2 to the printer PE terminal. **Never drill/screw into the tubes** (PTC chips + PI film inside). Check every tube/fin row to the PE pin of the plug < 0.5 Ohm (fins may be glued with non-conductive adhesive). Ideally 500 V insulation test L/N -> PE before first use. 30 mA RCD on the circuit (test button)
  - [ ] One-shot thermal fuse in series with L, clamped to the aluminium next to the bimetal: SANTE 10A 172 C 250 V axial, LCSC/JLC **C496729** (holding 142 C, so no nuisance trips with fan at 80-120 C; only opens if the bimetal fails). Crimp or heat-sink the leads when soldering
  - [ ] Klipper: draft ready in `printer_data/config/chamber_heater.cfg` (not included): SSR on E1-OUT `PC8`, fan on FAN1 `PB1` with tach on `PA1`, control sensor PC0 (chamber_air moves there), `CHAMBER_HEAT TARGET=` max 65 C (camera rated 70 C), fan-rpm guard, chamber_top `max_temp` 90 as backstop. Needs a 2nd SSR + a 24 V 4-wire fan
  - [ ] Mount on metal or PA66/PEEK standoffs: assume 230 C at the fins if the fan stops

### Future
- [ ] Filament inventory (`printer_data/config/orca_profiles/FILAMENT_INVENTORY.md`): fill in the amount left on the opened spools, find the 4th PrimaSelect red 1 kg and the 2nd PrimaSelect black 2.5 kg (bought 2025-04-11), photo of the transparent PLA label (#22, ScapeFill?). Per-brand Orca presets after flow/PA/max-flow calibration (PrimaSelect ABS first)
- [ ] Physical X/Y microswitch endstops, remove the DIAG jumpers when switching. X: switch on the CNC Tap V2 mount -> SB2040 ENDSTOP_1 `gpio29` (JP10, on-board 4.7k pull-up; NC switch: `SB2040:gpio29`, NO switch: `!SB2040:gpio29`). Y: switch on the rear gantry above motor A -> Spider Y- `PB13`. 2026-11-25: 4-core cable pulled through the Z drag chain with the new motors (Y signal + GND, 2 spare cores), **not plugged into the Spider yet** (X-/Y- ports share PB14/PB13 with the DIAG jumpers)
- [ ] Better toolhead board that fits the toolhead - the SB2040 cannot be mounted where it should because the Orbiter screw sits there (currently taped)
- [ ] Emergency stop: latching 2-pole NC mushroom switch cutting L+N before the PSU and the bed SSR (PE never switched)
- [ ] Restore Z `position_max` 340 when the chamber NTCs are moved
- [x] USB camera LED: **dropped 2026-11-24.** Vendor docs: one ~8 lm 3020 LED driven by the camera firmware; the installed V107 only flashes it on still capture, the only always-on firmware (V100) most likely has no microphone. The microphone matters more, so the camera stays on V107. Details in `printer_data/config/CAMERA_AUDIO.md`
- [x] USB camera microphone: go2rtc v1.9.14 installed 2026-11-18 (service `go2rtc`), video + sound at `http://<pi>:1984/stream.html?src=usbcam&mode=webrtc` (`go2rtc.yaml`, `CAMERA_AUDIO.md`)
- [x] go2rtc webcam "USB Cam + ljud" in Mainsail with sound: player patched with `printer_data/config/system/mainsail_go2rtc_audio_patch.sh` (**re-run after Mainsail updates**)

### On site - power OFF
- [x] USB cam (UICPAL OV5648, LED + mic on board): plug into the Pi, then read `lsusb -v` / `v4l2-ctl --list-ctrls` / `arecord -l` to find the LED control (likely a UVC extension unit) and test the mic. Add as cam 2 in crowsnest
- [x] Check the X rail is **MGN12H** (required for CNC Tap V2)
- [x] Clean and grease all linear rails, check belts and printed parts for cracks
- [x] Clean the Orbiter drive gears
- [ ] Gantry NTC (already in the Z drag chain): printed standoff on the gantry extrusion, connect to Spider T1 `PC1` in place of `chamber_side`, rename the sensor `chamber_gantry` in `chamber_sensors.cfg`, compare with `chamber_air` during a heatsoak
- [ ] Chamber NTCs: fit 3 x NTC 100K temporarily (PC0 rear mid, PC1 side mid, PC2 top), compare during a heatsoak, keep the best as `chamber_air` - see `chamber_sensors.cfg`. Check gantry clearance, cable length to the electronics bay
- [x] Hotend fan fitted 2026-11-17 (tach not wired yet)
- [ ] Part fan 5015 (see `fan_upgrade.cfg`)
- [ ] Hotend fan tach -> SB2040 ENDSTOP_2 `gpio25` (JP11 pin 1, see the wiring notes above), then enable `tachometer_pin: ^SB2040:gpio25` (watchdog in `hotend_fan_alarm.cfg`)

### On site - heaters only, bed empty
- [ ] Bed `max_power` 0.6 -> 1.0 + `PID_CALIBRATE HEATER=heater_bed TARGET=110`, check electronics fans start at bed > 45 C
- [ ] Hot-tighten the nozzle at 250 C, hotend PID (hotend overshoots ~12 C with the old PID values)
- [ ] Hot bed mesh at 100 C (cold nozzle, Tap) to see the bed warp

### Needs motion
- [x] Test and enable `homing_v2.cfg` (2026-11-17)
- [ ] Test and enable `load_unload_filament_v2.cfg`
- [ ] Belt tension ~110 Hz over 150 mm, A/B within 2 Hz: `tools/belt_freq.py` (camera mic) or a phone app
- [x] Belt tension panel layout (fixed 2026-11-26: separate views - overview, one-belt view, guided A/B check, position setup; fixed-height buttons)
- [ ] Belt tension tool upstream: after real-belt tests, publish as a standalone repo (install script, Moonraker update_manager, configurable ALSA device, no hard-coded paths), then offer the panel to KlipperScreen as a PR (needs translations; numpy is not in the KlipperScreen env, so the analysis stays a separate script)
- [ ] Belt sensor board (idea): small USB board, enumerates as a standard USB audio device so `belt_freq.py` works unchanged. RP2040 + PDM MEMS mic (TinyUSB UAC) close to the belt, optional IR reflective sensor that sees the belt vibrate directly (immune to the ~82 Hz ambient hum). Magnet/clip mount, moved between the A/B spans. Try a cheap USB lavalier mic first
- [ ] Homing repeat test after the motor swap: `tools/homing_test.sh 10` (stops at the first error)
- [x] `SHAPER_CALIBRATE` + `SAVE_CONFIG` (2026-11-17, provisional - redo when the toolhead is finished, X with `FREQ_END=170`)
- [ ] Extruder `rotation_distance`, then OrcaSlicer flow, PA and max volumetric flow tests
- [ ] Enable `heatsoak.cfg` + `print_start_v2.cfg` (rename old macro to `PRINT_START_OLD`), test with an ABS print

### Rebuild (after the printer prints reliably again)
- [ ] OS migration on a new SD card (`OS_MIGRATION.md`), before reflashing the MCUs
- [ ] Print parts: Stealthburner Rapido UHF (4010 version), wide-mouth 5015 duct, brush mount
- [ ] UHF toolhead + CNC Tap V2 + shielded CAN cable + HoneyBadger 5015 + nozzle brush/KOMB
  - Config after the swap (Tap config itself stays - same probe on `SB2040:gpio28`):
    `QUERY_PROBE` open/triggered by hand (if inverted: `pin: ^!SB2040:gpio28`), `PROBE_ACCURACY` (range < 0.01),
    `Z_ENDSTOP_CALIBRATE` / new `z_offset`, hotend `PID_CALIBRATE` at 250 C, enable `fan_upgrade.cfg`,
    measure brush position for KOMB, re-run pressure advance + max flow (UHF melts more)
- [ ] Spider: permanent USB cable + Katapult so it can be flashed from the Pi (FLASHING.md option A)
- [ ] Reflash Spider and SB2040 firmware to the current Klipper version (canserial buffer fix)
- [ ] If CAN errors remain: USB-CAN adapter (Mellow UTOC / BTT U2C) instead of the MCP2515 HAT
- [ ] Fume filtration (Nevermore / exhaust fan - config sections already prepared)

## Extras <BR>
- [Make Klipper run on a single core for itself](https://canbus.esoterical.online/troubleshooting/timeout_during_homing_probing.html#:~:text=Go%20through%20the%20steps%20in%20reverse%20order%20%28re-enable,the%20limits%20of%20what%20your%20Pi%20can%20handle)
  - Fixed 2026-11-13: `/etc/systemd/system/klipper.service.d/override.conf` had the header `service]` instead of `[Service]`, so `CPUAffinity=3` was ignored. Fix used:
    ```bash
    sudo sed -i 's/^service]$/[Service]/' /etc/systemd/system/klipper.service.d/override.conf
    sudo systemctl daemon-reload && sudo systemctl restart klipper
    systemctl show klipper -p CPUAffinity   # should print CPUAffinity=3
    ```
  - Optional: add `isolcpus=3` to `/boot/cmdline.txt` so nothing else runs on core 3.

CANbus
- Use ```ip -s link show can0``` to show can traffic
