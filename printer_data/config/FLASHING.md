# MCU firmware flashing plan

Written 2026-11-13. Host Klipper is v0.13.0-827; the boards still run
v0.13.0-120 (Spider) and v0.13.0-112 (SB2040). That works, but the next
firmware build gives e.g. the larger CAN transmit buffer (canserial 192 bytes).
Do this during the rebuild, with the printer idle and someone on site.

## Current state

| Board | MCU | Bootloader | Link to Pi | Flash from Pi today? |
|---|---|---|---|---|
| Mellow SB2040 v1 | RP2040 | **CanBoot** (old name of Katapult), app at `0x10004000` (16 KiB) | CAN `can0`, 1 Mbit, uuid `ea913f6d2453` | **Yes** - already done this way before |
| FYSETC Spider v1.1 | STM32F446, 12 MHz crystal | FYSETC SD-card bootloader, app at `0x08008000` (32 KiB) | UART `/dev/ttyAMA0` (USART1 PA9/PA10), 250000 baud | **No** - needs SD card or DFU jumper |

Note: `~/klipper/.config` is currently for an **STM32G474** (another board) and
owned by root. Keep one saved config per board (see below) so this cannot be
mixed up.

## Saved build configs (one-time)
```bash
sudo chown voron:voron ~/klipper/.config
cd ~/klipper
make menuconfig KCONFIG_CONFIG=config.sb2040
#   Micro-controller: Raspberry Pi RP2040/RP235x
#   Bootloader offset: 16KiB bootloader
#   Communication interface: CAN bus  (CAN RX gpio4, CAN TX gpio5)
#   CAN bus speed: 1000000
make menuconfig KCONFIG_CONFIG=config.spider
#   Micro-controller: STMicroelectronics STM32, Processor: STM32F446
#   Bootloader offset: 32KiB bootloader (FYSETC)   <- or Katapult offset, see option A
#   Clock reference: 12 MHz crystal
#   Communication interface: Serial (on USART1 PA10/PA9)   <- or USB, see option A
#   Baud rate: 250000
```

## SB2040 - flash over CAN (works today)
```bash
sudo systemctl stop klipper
cd ~/klipper
make clean KCONFIG_CONFIG=config.sb2040 && make KCONFIG_CONFIG=config.sb2040 -j4
python3 ~/CanBoot/scripts/flash_can.py -i can0 -u ea913f6d2453 -f ~/klipper/out/klipper.bin
python3 ~/CanBoot/scripts/flash_can.py -i can0 -q   # Klipper should answer again with the same uuid
sudo systemctl start klipper
```
Recovery if it ever fails: USB-C cable to the Pi, hold BOOT while powering on,
flash `klipper.uf2` (or `~/CanBoot/out/canboot.uf2` to restore the bootloader).

## Spider - options to flash it from the Pi

### Option A (recommended): permanent USB cable + Katapult
"Build": one USB-A -> USB-C cable between the Pi and the Spider, left plugged in.
1. One-time on site: BOOT0 jumper to 3.3 V, press reset -> STM32 ROM DFU.
   Flash Katapult (STM32F446, 12 MHz, USB, app offset 32 KiB) with `dfu-util`.
   Remove the jumper.
2. Rebuild Klipper for the Spider with **USB** communication and the Katapult
   offset, flash it via Katapult.
3. printer.cfg `[mcu] serial:` -> `/dev/serial/by-id/usb-Klipper_stm32f446xx_...`
4. From then on, from the Pi, without touching the printer:
   ```bash
   python3 ~/katapult/scripts/flashtool.py -r -d /dev/serial/by-id/usb-Klipper_stm32f446xx_...   # request bootloader
   python3 ~/katapult/scripts/flashtool.py -d /dev/serial/by-id/usb-katapult_stm32f446xx_... -f ~/klipper/out/klipper.bin
   ```
- Recovery stays simple: the same cable + the BOOT0 jumper always gives DFU.
- The UART wires can stay connected as a fallback.
- Check before plugging in: the Spider's USB 5 V jumper/setting, so the Pi
  does not back-feed the board's 5 V rail (verify on the board/manual).
- CanBoot has been renamed Katapult: clone `https://github.com/Arksine/katapult`
  into `~/katapult` (the old `~/CanBoot` keeps working for the SB2040).

### Option B: keep the UART, add BOOT0 + RESET wires to Pi GPIOs
The STM32's built-in ROM bootloader also listens on USART1 (PA9/PA10) - the
same pins the Pi already uses. Two extra wires from Pi GPIOs to BOOT0 and NRST
let the Pi put the chip into the ROM bootloader and flash with `stm32flash`.
- Pros: no USB, cannot brick (ROM bootloader).
- Cons: DIY wiring to small pads, GPIO handling via `pinctrl`/`gpioset`
  (sysfs GPIO is gone in newer Pi kernels), some reports of flaky F446 USART1
  ROM bootloader behaviour. Not recommended over option A.

### Option C (recovery tool): Pi as SWD programmer
OpenOCD can drive SWD directly from Pi GPIOs (`bcm2835gpio`): SWDIO (PA13),
SWCLK (PA14), NRST, GND. That can recover any STM32 board even with a broken
bootloader. Only worth wiring if the Spider has an accessible SWD header -
check on site.

## Order on flash day
1. Printer idle, heaters off, Klipper stopped.
2. SB2040 over CAN.
3. Spider (option A once set up, otherwise SD card: copy `out/klipper.bin` as
   `firmware.bin` to a FAT32 SD card, insert, power-cycle; it is renamed to
   `firmware.cur` when done).
4. Start Klipper and check that both MCUs report the new version
   (Mainsail -> Machine -> System loads / `klippy.log`).
