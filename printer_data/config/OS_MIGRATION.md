# OS migration plan: Bullseye -> MainsailOS v3 (Debian 13 Trixie)

Written 2026-11-14. Status: PLAN, nothing done yet. Do it on site.

## Why
The Pi runs Raspberry Pi OS 11 (Bullseye, arm64, kernel 6.1). Bullseye LTS
security support ended in August 2026: no more security updates, and new
Klipper/Moonraker/crowsnest versions are increasingly tested only on newer
Python and libcamera versions.

## Choice: MainsailOS v3.0 (arm64) on a NEW SD card
- MainsailOS v3.0.0 (May 2026) is based on Debian 13 Trixie and ships
  Klipper, Moonraker, Mainsail, crowsnest, Sonar and timelapse preinstalled.
- The MainsailOS team recommends a fresh image, not a dist-upgrade. That
  fits: the **old SD card stays untouched as an instant rollback** (swap the
  card back and everything is as before).
- Alternative: Raspberry Pi OS Lite (Trixie, 64-bit) + KIAUH. More manual
  work, same result. Only pick it if MainsailOS gives problems.
- Card: a new good A2 card (Samsung PRO Endurance / SanDisk High Endurance),
  32-64 GB. The current card is a generic 32 GB "SD32G". A USB SSD is also an
  option on a Pi 4 (faster and more durable), but needs a free USB port.

## Known risks on Trixie
| Area | Risk | Plan |
|---|---|---|
| Pi cam (camera-streamer) | libcamera updates on Pi OS often break camera-streamer until it is rebuilt; libcamera 0.7 needed a C++20 patch (crowsnest issue #344) | Test the Pi cam first. Fallback: the USB OV5648 cam with `ustreamer` (no libcamera involved) |
| CAN interface | `/etc/network/interfaces.d` (ifupdown) is not used on new images | systemd-networkd files, see step 4 |
| config.txt | Moved to `/boot/firmware/config.txt` | Same lines, new path |
| KlipperScreen (BTT Pi TFT50) | Must be installed separately (KIAUH) | Test touch + display after install |
| MCU firmware | New host Klipper will be newer than the MCU firmware | Flash both boards with a fresh build (FLASHING.md) |
| Python 3.13 | Klipper/Moonraker venvs are rebuilt by the installer | Nothing extra |

## Inventory of what has to be carried over
Non-secret system files are already copied to `printer_data/config/system/`
(backed up to GitHub):

| File in `system/` | Goes to | What |
|---|---|---|
| `boot-config.txt` | reference for `/boot/firmware/config.txt` | SPI, MCP2515 overlay (12 MHz, int 25, 10 MHz SPI), UART + disable-bt, I2C |
| `can0.interfaces` | rewrite as systemd-networkd (step 4) | can0 1 Mbit, txqueuelen 1024 |
| `klipper.service.d-override.conf` | `/etc/systemd/system/klipper.service.d/override.conf` | Klipper pinned to CPU core 3 |
| `crowsnest.service.d-boot-delay.conf` | `/etc/systemd/system/crowsnest.service.d/` | 10 s start delay (Pi cam boot hang) |
| `moonraker-db-backup.service/.timer`, `moonraker_db_backup.sh` | `/etc/systemd/system/`, `~/` | Daily Moonraker DB backup |
| `070-wifi-powersave.rules` | `/etc/udev/rules.d/` | WiFi power save off |
| `sudoers-010_voron-printer` | `/etc/sudoers.d/` (check with `visudo -c`) | Passwordless service restarts |

**Secrets - NOT in GitHub, copy to the PC (or a USB stick) before the swap:**
- `/etc/wireguard/wg0.conf` (WireGuard VPN, `wg0` 10.0.0.9, `wg-quick@wg0` enabled)
  - also a copy in `~/wg0.conf`
- `~/klipper-backup/.env` (GitHub token for the config backup)
- `~/.ssh/authorized_keys` (if SSH keys are used)

**Data (optional):**
- `~/printer_data/gcodes` - 1.1 GB, `~/printer_data/timelapse` - 112 MB
- Moonraker database (print history, Mainsail settings, webcam settings) -
  daily backup in `~/printer_data/backup/database/moonraker-db.sqlite` + GitHub

**Extra software (not part of MainsailOS):**
- Klipper-Adaptive-Meshing-Purging (KAMP) - `printer_data/config/KAMP` is a symlink to it
- klipper-backup (+ filewatch and on-boot services)
- KlipperScreen
- CanBoot/Katapult scripts (`flash_can.py` for the SB2040)
- KOMB is plain config in `printer_data/config/KOMB` (comes with the config)

## Steps on migration day
1. **Old system, last time:** stop prints. Run `~/moonraker_db_backup.sh`
   (DB + config to GitHub). Copy the secrets above to the PC. Optionally
   `scp` the gcodes folder. Shut down, take the card out and **label it**.
2. **Flash** MainsailOS v3 arm64 with Raspberry Pi Imager. In the Imager
   settings: user **`voron`** (keeps all paths `/home/voron/...` identical),
   hostname, WiFi (country SE), SSH on.
3. **First boot:** `sudo apt update && sudo apt full-upgrade`, then add to
   `/boot/firmware/config.txt`:
   ```
   dtparam=spi=on
   dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=10000000
   enable_uart=1
   dtoverlay=disable-bt
   dtparam=i2c_arm=on
   ```
   and remove `console=serial0,115200` from `/boot/firmware/cmdline.txt` if
   present (the Spider uses that UART). Disable the serial console in
   `raspi-config` -> Interface -> Serial: login shell **no**, hardware **yes**.
4. **CAN with systemd-networkd** (Klipper docs method):
   ```
   # /etc/systemd/network/80-can.network
   [Match]
   Name=can0
   [CAN]
   BitRate=1M
   ```
   ```
   # /etc/udev/rules.d/10-can.rules
   SUBSYSTEM=="net", ACTION=="change|add", KERNEL=="can*", ATTR{tx_queue_len}="1024"
   ```
   `sudo systemctl enable --now systemd-networkd`, reboot. Check:
   `ip -d -s link show can0` (UP, 1000000, txqueuelen 1024) and
   `ls -l /dev/ttyAMA0`.
5. **Config back:** clone the GitHub config repo and copy
   `printer_data/config/*` into place (or the klipper-backup restore
   function). Install KAMP, klipper-backup, KlipperScreen (KIAUH), CanBoot or
   Katapult. Re-create the symlinks (`KAMP`, `timelapse.cfg`, `mainsail.cfg`).
6. **Moonraker DB:** copy `moonraker-db.sqlite` to
   `~/printer_data/backup/database/` and restore it with the Moonraker API
   `POST /server/database/restore?filename=moonraker-db.sqlite`.
7. **System files** from `system/` (table above), `sudo systemctl daemon-reload`,
   enable `moonraker-db-backup.timer`, WireGuard: `sudo apt install wireguard`,
   copy `wg0.conf`, `sudo systemctl enable --now wg-quick@wg0`.
8. **Test (no motion needed):** Klipper connects to both MCUs, temperatures
   OK, CAN errors 0 (`ip -s link show can0`), Pi cam stream + snapshot,
   KlipperScreen, WireGuard reachable, backup push works.
9. **Firmware:** build fresh images from the new Klipper with the configs in
   `printer_data/config/firmware/` and flash (FLASHING.md).

## Rollback
Power off, put the old SD card back, power on. Nothing on the old card is
changed by any of the steps above.

## Sources
- MainsailOS v3.0.0 announcement: https://github.com/orgs/mainsail-crew/discussions/2485
- MainsailOS releases: https://github.com/mainsail-crew/mainsailos/releases
- crowsnest on Trixie / libcamera 0.7: https://github.com/mainsail-crew/crowsnest/issues/344
- Klipper CAN host setup: https://www.klipper3d.org/CANBUS.html
