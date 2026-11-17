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
- [OMRON G3NB-225B-1 25A SSR](https://www.omron-ap.com/products/family/3232/download/catalog.html)

### Fans
| Position | Fan | Pin | Status |
|---|---|---|---|
| Hotend (lower, 4010 axial) | [HoneyBadger 4010A-24-9400 "High SP & Tach"](https://3do.dk/en/fans/1145-4010-axial-fan-24v-by-honeybadger-high-sp-9400-rpm.html), 3-wire, not PWM | SB2040 fan adapter "Hotend Fan1": red -> 24V, black -> AGND (switched GND, `gpio14`); white tach **not connected** yet | **Installed 2026-11-17**, tested: on at 50 C, off below 50 C |
| Part cooling (upper, 5015 blower) | [HoneyBadger 5015 blower 9200 RPM, 4-wire PWM/tach, wide mouth](https://3do.dk/en/fans/4366-5015-blower-fan-by-honeybadger-9200-rpm-4-wires-pwmtach-wide-mouth.html) | SB2040 power `gpio13`, PWM `gpio17` | Ordered 2026-11-13 - duct needs adapting for the wide mouth |
| Electronics bay | Kit 6020 fans | Spider `PB2` (on when bed > 45 C) | Check that they still spin |
| Nevermore Duo | 2 x blower | Spider FAN0 `PB0` | Installed 2026-11-17 |

Hotend fan config: `printer.cfg` `[heater_fan hotend_fan]` (wiring in the comments). Stall watchdog: `hotend_fan_alarm.cfg` (included, but idle until the tach is wired).

**Hotend fan wiring notes (learned the hard way, 2026-11-17):**
- On the Mellow fan adapter, "AGND" is the *switched* fan ground (low-side MOSFET), not analog ground. 2-wire / non-PWM fans go 24V + AGND.
- The adapter's "3 Line: S = PWM" row is for PWM fans only. A tach wire must **never** go to PWM0/PWM1: with the white tach on PWM0 (`gpio16`) the SB2040 MCU temperature read 120-135 C and Klipper shut down.
- The adapter has no tach input. To enable the watchdog, run the white wire to the main board endstop header "1" (LIMIT_1, `gpio29`) and uncomment `tachometer_pin` / `tachometer_ppr` in `printer.cfg`.

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
Status 2026-11-17: printer homes, levels and probes again; hotend fan replaced; input shaper provisional. Remaining before printing: part fan, nozzle hot-tighten, hotend PID, extruder calibration, ABS test print.

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

### Future
- [ ] Physical X/Y microswitch endstops (BIQU CNC Tap V2 includes an X endstop arm; X -> Spider PB14, Y -> PB13, remove DIAG jumpers)
- [ ] Emergency stop: latching 2-pole NC mushroom switch cutting L+N before the PSU and the bed SSR (PE never switched)
- [ ] Restore Z `position_max` 340 when the chamber NTCs are moved
- [ ] USB camera LED: not controllable over USB (Realtek RTS58xx XU is a register/flash mailbox - never write to it). Rewire the LED to a Klipper output (e.g. a free Spider/SB2040 pin via a MOSFET) and add an `output_pin`
- [ ] USB camera microphone (ALSA card 3, works, ~-37 dBFS with fans running): get audio into Mainsail/Klipper (e.g. a stream with audio alongside ustreamer, or a Moonraker-side noise/knock monitor)

### On site - power OFF
- [x] USB cam (UICPAL OV5648, LED + mic on board): plug into the Pi, then read `lsusb -v` / `v4l2-ctl --list-ctrls` / `arecord -l` to find the LED control (likely a UVC extension unit) and test the mic. Add as cam 2 in crowsnest
- [x] Check the X rail is **MGN12H** (required for CNC Tap V2)
- [x] Clean and grease all linear rails, check belts and printed parts for cracks
- [x] Clean the Orbiter drive gears
- [ ] Chamber NTCs: fit 3 x NTC 100K temporarily (PC0 rear mid, PC1 side mid, PC2 top), compare during a heatsoak, keep the best as `chamber_air` - see `chamber_sensors.cfg`. Check gantry clearance, cable length to the electronics bay
- [x] Hotend fan fitted 2026-11-17 (tach not wired yet)
- [ ] Part fan 5015 (see `fan_upgrade.cfg`)
- [ ] Hotend fan tach: white wire -> SB2040 endstop header "1" (gpio29), then enable `tachometer_pin` (watchdog in `hotend_fan_alarm.cfg`)

### On site - heaters only, bed empty
- [ ] Bed `max_power` 0.6 -> 1.0 + `PID_CALIBRATE HEATER=heater_bed TARGET=110`, check electronics fans start at bed > 45 C
- [ ] Hot-tighten the nozzle at 250 C, hotend PID (hotend overshoots ~12 C with the old PID values)
- [ ] Hot bed mesh at 100 C (cold nozzle, Tap) to see the bed warp

### Needs motion
- [x] Test and enable `homing_v2.cfg` (2026-11-17)
- [ ] Test and enable `load_unload_filament_v2.cfg`
- [ ] Belt tension with the FYSETC gauge: ~110 Hz over 150 mm, A/B within 2 Hz
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
