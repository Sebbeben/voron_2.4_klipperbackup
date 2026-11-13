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
- [Mellow SB2040 v1](https://mellow-3d.github.io/fly_sb2040_v1_general.html) (CAN, 1 Mbit) - [pin definitions](https://mellow-3d.github.io/fly_sb2040_v1_pins.html)
- Orbiter extruder (version to be verified - `rotation_distance: 4.637` is the Orbiter 2.0 value)
  - [FYSETC G36HSY4405-6D-1200 stepper motor](https://github.com/FYSETC/FYSETC-MOTORS/blob/main/G36HSY4405-6D-1200/G36HSY4405-6D-1200.pdf), run at 0.65 A
- [Rapido UHF Hotend](https://www.phaetus.com/products/rapido-hotend?variant=45122834465045) (v1, HF + UHF nozzles included)
  - Currently: temporary V6 0.4 mm nozzle; plan: HF nozzle back, then UHF with a new toolhead
- [BTT Pi Screen 5"](https://github.com/bigtreetech/BIGTREETECH-TouchScreenHardware/tree/master/BTT%20Pi%20TFT50%20V2.0%20Github/Hardware)
- [Chaotic Labs Voron Tap V2.0 with OptoTap v2.1](https://github.com/Chaoticlab/CNC-Tap-for-Voron) (5 V)
- CNC Aluminium Idlers
- [Meanwell LRS-200-24 psu](https://meanwell-ps.com/products/lrs-200-24)
- [Voron Daylight on a stick XXL](https://github.com/VoronDesign/Voron-Hardware/tree/master/Daylight) (`output_pin daylight`, PB15)
- Pi Cam (OV5647, 1280x720 @ 15 fps via Crowsnest)
- [OMRON G3NB-225B-1 25A SSR](https://www.omron-ap.com/products/family/3232/download/catalog.html)

### Fans
| Position | Fan | Pin | Status |
|---|---|---|---|
| Hotend (lower, 4010 axial) | [HoneyBadger 4010 axial 24V High SP 9400 RPM](https://3do.dk/en/fans/1145-4010-axial-fan-24v-by-honeybadger-high-sp-9400-rpm.html) | SB2040 `gpio14` (+ tach `gpio29`) | Ordered 2026-11-13 - replaces a dead sleeve-bearing fan |
| Part cooling (upper, 5015 blower) | [HoneyBadger 5015 blower 9200 RPM, 4-wire PWM/tach, wide mouth](https://3do.dk/en/fans/4366-5015-blower-fan-by-honeybadger-9200-rpm-4-wires-pwmtach-wide-mouth.html) | SB2040 power `gpio13`, PWM `gpio17` | Ordered 2026-11-13 - duct needs adapting for the wide mouth |
| Electronics bay | Kit 6020 fans | Spider `PB2` (on when bed > 45 C) | Check that they still spin |

Config for the new fans is prepared (commented out) in `fan_upgrade.cfg`, including a hotend fan watchdog that pauses the print if the fan stalls.

## Hardware *Not installed*
- [BIQU CNC Voron Tap V2](https://github.com/Chaoticlab/CNC-Tap-for-Voron/tree/master/STL/CNC_VORON_TAP_V2) - plan: fit together with the UHF toolhead
- Voron 2.4 silicone nozzle brush kit ([print files](https://www.thingiverse.com/thing:6724416)) - KOMB macro is already installed
- Mellow 3 m shielded twisted-pair CAN cable (20CANW3M) - plan: replace the current CAN cable
- OV5648 USB camera, 5 MP autofocus, 120 degrees
- FYSETC belt tension gauge (tool)
- Spare Orbiter motor: FYSETC 36STH20-1004AHG
- Simple filament runout switch
- Voron PT100 Stick
- Fysetc CNC Aluminium Clockwork extruder
- Unused kit parts: BMG extruder kit + 42HS20401B motor, E3D V6 hotend

## Klipper Mods
- [Klipper-backup](https://github.com/Staubgeborener/Klipper-Backup)
- [Klipper-Adaptive-Meshing-Purging (KAMP)](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging) - Smart_Park is used in `PRINT_START`
- [KOMB](https://github.com/TmRxJD/KOMB) nozzle brushing macro - installed in `KOMB/`, not enabled yet
- [Filament dryer macro](https://gist.github.com/NameOfTheDragon/e579295549aaa19b3f41ae07b8f3cbd6#file-filament_dryer-cfg) - `DRY_ABS` = bed 95 C for 5 h (spool on a spacer, door slightly open)
- Crowsnest, Moonraker-timelapse, Sonar, KlipperScreen

## Printed Mods
- [Orbitu for Stealthburner Orbiter extruder](https://github.com/Saccco/VoronUsers/tree/master/printer_mods/Saccco/Orbitu)
- Planned: [Voron Stealthburner Rapido UHF](https://www.printables.com/model/1272320-voron-stealthburner-rapido-uhf) (4010 hotend fan version)

## Maintenance log

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
Status 2026-11-13: toolhead disassembled, **no motor movement** for a few days.

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

### On site - power OFF
- [ ] USB cam (UICPAL OV5648, LED + mic on board): plug into the Pi, then read `lsusb -v` / `v4l2-ctl --list-ctrls` / `arecord -l` to find the LED control (likely a UVC extension unit) and test the mic. Add as cam 2 in crowsnest
- [ ] Check the X rail is **MGN12H** (required for CNC Tap V2)
- [ ] Clean and grease all linear rails, check belts and printed parts for cracks
- [ ] Clean the Orbiter drive gears
- [ ] Fit the chamber NTC (spare HT-NTC100K) on Spider T0 / PC0, mid-height side panel
- [ ] Fit new fans when delivered (see `fan_upgrade.cfg` for wiring)

### On site - heaters only, bed empty
- [ ] Bed `max_power` 0.6 -> 1.0 + `PID_CALIBRATE HEATER=heater_bed TARGET=110`, check electronics fans start at bed > 45 C
- [ ] After the new hotend fan: enable `fan_upgrade.cfg`, test fan + watchdog, hot-tighten the nozzle at 250 C, hotend PID

### Needs motion
- [ ] Test and enable `homing_v2.cfg` and `load_unload_filament_v2.cfg`
- [ ] Belt tension with the FYSETC gauge: ~110 Hz over 150 mm, A/B within 2 Hz
- [ ] `SHAPER_CALIBRATE` + `SAVE_CONFIG` (input shaper has never been active)
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
