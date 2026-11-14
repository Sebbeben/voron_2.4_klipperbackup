# OrcaSlicer profiles - Voron 2.4 350 (Rapido HF 0.4)

Created 2026-11-13. They replace the Cura profile "Voron 2.4 350 ABS".
All presets inherit Orca's own system presets (`Voron 2.4 350 0.4 nozzle`,
`0.20mm Standard @Voron`, `Generic <material> @System`), so only the
differences are stored here.

## Import
1. Download this folder (Mainsail -> Machine -> `orca_profiles`).
2. OrcaSlicer: add the system printer **Voron 2.4 350 0.4 nozzle** first
   (Printer -> Add/Remove printers -> Voron). The user presets inherit from it.
3. File -> Import -> Import Configs... -> select all `.json` files.
4. Select printer `Voron 2.4 350 Rapido 0.4`, process
   `0.20mm Strong @Voron 2.4 350 Rapido` and a filament `... @Voron 2.4 350 Rapido`.
5. Printer settings -> Physical printer: Klipper/Moonraker, host = the Pi's IP
   (upload + start directly from Orca).

Check after import: Orca may show some values as modified/red if the
installed Orca version stores them differently. The values below are the ones
that matter.

## What is different from Cura
| | Cura (old) | Orca (new) |
|---|---|---|
| Accelerations | set in profile but **never sent** (`acceleration_enabled = False`) | sent per feature: outer wall 2000, rest 3000, first layer 500 |
| Speed limit | none, infill 300 mm/s (~22 mm3/s) | capped by filament max volumetric speed |
| ABS nozzle | 240 C | 250 C (255 first layer) |
| Heat soak | `CHAMBER=5/20` -> skipped | `SOAK=20` min for ABS/ASA/PC/PA (used once `heatsoak.cfg` is enabled) |
| Arc welder | on | off (no benefit with Klipper) |
| Start gcode | `#; M190` workaround | `M190 S0` / `M109 S0` stop Orca from adding its own heat-up |

## Filament start values (to be calibrated)
| Profile | Nozzle | Bed | Fan | Max flow mm3/s | Notes |
|---|---|---|---|---|---|
| ABS | 250 / 255 | 105 / 110 | 15-40 % | 15 | enclosure closed |
| ASA | 255 / 260 | 105 / 110 | 20-50 % | 15 | enclosure closed |
| PLA | 215 / 220 | 60 / 65 | 100 % | 15 | **door/lid open** - heat creep risk |
| PETG | 240 / 245 | 80 / 85 | 30-60 % | 12 | textured PEI |
| TPU 95A | 230 | 50 | 50-100 % | 3.5 | short retraction, no z-hop |
| PA Nylon | 260 | 90 | 0-20 % | 8 | **dry first**, glue stick |
| POM | 220 / 225 | 110 | 0-20 % | 8 | experimental, needs special build surface |

Flow ratio is 0.92 (old Cura value) until the extruder `rotation_distance`
is calibrated. TPU uses 1.0.

## Calibration order (once the printer moves)
1. Extruder `rotation_distance` in Klipper (then set flow ratio back towards 1.0)
2. Orca -> Calibration -> Temperature tower (per material)
3. Orca -> Calibration -> Max volumetric speed -> set ~80 % of the result
4. Orca -> Calibration -> Pressure advance (per material) -> enable PA in the filament profile
5. Orca -> Calibration -> Flow rate (pass 1 + 2)
6. After input shaper: raise accelerations here **and** `max_accel` in printer.cfg
