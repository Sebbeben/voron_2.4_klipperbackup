# USB camera: audio + LED

Camera: "UICPAL" OV5648 5 MP AF, USB 0edc:2050, iManufacturer `YJXU502S`, Realtek RTS58xx bridge.
Video via crowsnest `[cam 2]` (ustreamer, port 8081, 1920x1080 @ 15). Microphone = ALSA card `Camera`
(`plughw:CARD=Camera,DEV=0`), works, about -37 dBFS with the fans running.

Status 2026-11-18: **go2rtc v1.9.14 installed and running** as systemd service `go2rtc` (unit file copy in
`system/go2rtc.service`). Video is H.264 960x540 (software x264, keyframe every 2 s, ~65 % of one core while
watched) via an `exec:` ffmpeg command, because go2rtc 1.9.14 rejects the Bullseye ffmpeg 4.3 for `ffmpeg:`
sources ("unsupported version"); the Pi hardware encoder sent SPS/PPS only once (late viewers: endless spinner). Internal RTSP on
127.0.0.1:8556 (8554 = crowsnest cam 1).

## Audio (and video) over WebRTC with go2rtc

Config is ready: `go2rtc.yaml` (this folder).

- Stream `usbcam`: video from ustreamer (MJPEG -> H.264 1280x720, Pi 4 hardware encoder `h264_v4l2m2m`)
  plus the microphone as Opus.
- Stream `usbcam_audio`: microphone only.
- Both ffmpeg chains were tested on the Pi on 2026-11-17 (Opus file OK, 45 frames H.264 720p OK).
  Transcoding costs ~40 % of one core, and go2rtc only runs ffmpeg while someone is watching.

### Install (Pi, no sudo needed except the service file)

```
mkdir -p ~/go2rtc && cd ~/go2rtc
curl -L -o go2rtc https://github.com/AlexxIT/go2rtc/releases/download/v1.9.14/go2rtc_linux_arm64
chmod +x go2rtc
./go2rtc -config ~/printer_data/config/go2rtc.yaml     # test, then Ctrl+C
```

systemd service `/etc/systemd/system/go2rtc.service`:

```
[Unit]
Description=go2rtc (USB camera WebRTC + audio)
After=network-online.target crowsnest.service

[Service]
User=voron
ExecStart=/home/voron/go2rtc/go2rtc -config /home/voron/printer_data/config/go2rtc.yaml
Restart=always
Nice=10

[Install]
WantedBy=multi-user.target
```

`sudo systemctl daemon-reload && sudo systemctl enable --now go2rtc`

### Watching / listening

- go2rtc web UI with sound and player controls: `http://<pi>:1984/stream.html?src=usbcam&mode=webrtc`
  (microphone only: `src=usbcam_audio`).
- Mainsail: new webcam, service "WebRTC (go2rtc)", URL `http://<pi>:1984/api/webrtc?src=usbcam`,
  enable audio. NOTE: Mainsail v2.19's go2rtc player creates the `<video>` element with `muted`, so in
  Mainsail you get the video but probably no sound; use the go2rtc page for sound.
- Security: the go2rtc API can start processes (`exec:`). Keep port 1984 on the LAN / WireGuard only,
  never port-forward it.

### Mainsail (sound in the Mainsail UI) - done 2026-11-18
- Webcam "USB Cam + ljud" added via Moonraker (`/server/webcams/item`): service `webrtc-go2rtc`,
  URL `/go2rtc/api/webrtc?src=usbcam` (nginx proxy, see below), `extra_data.enableAudio: true`.
- Mainsail v2.19 creates the go2rtc `<video>` muted and without controls, so the sound could never be
  turned on. `system/mainsail_go2rtc_audio_patch.sh` adds `controls` to the player (video still autoplays
  muted; click the speaker icon). **Re-run the script after every Mainsail update**, then reload the
  browser with the cache cleared (service worker).
- Play/pause and the timeline are hidden with `.theme/custom.css` (Chromium browsers); the patch also sets
  `controlslist="nodownload noplaybackrate noremoteplayback"` and disables picture-in-picture.
- nginx proxies go2rtc at `/go2rtc/` (installed with `system/install_nginx_go2rtc.sh`, backup
  `/etc/nginx/sites-available/mainsail.before_go2rtc`). Works on LAN and over WireGuard, and passes go2rtc's
  WebSocket origin check (a direct `http://192.168.0.7:1984` URL failed from 10.0.0.9: "origin not allowed").

### Ubuntu later (same support)

go2rtc is a single binary for amd64 as well (`go2rtc_linux_amd64`). On a PC the camera is not shared with
ustreamer, so use the device directly in the stream, e.g.
`ffmpeg:device?video=/dev/v4l/by-id/usb-YJXU502S_USB_Camera_20190415-video-index0#video=h264`
plus the same `exec:ffmpeg -f alsa ... plughw:CARD=Camera,DEV=0 ...` audio line. Desktop apps (Cheese,
OBS, guvcview) see the camera (UVC) and the microphone (USB Audio) without any driver.

## Vendor documents (received 2026-11-24)

Unpacked in `~/camera_docs/vendor_20261124/` (zip from the seller: product spec PDF, LED datasheet,
two firmware packages, Windows tools `amcap v3.0.9.exe` and `UvcCamDownload_AllInOne_RsProxy.exe` - not run).

**Module:** YJX-C5M / board "YJX-C5", maker 深圳市永吉星光电 (Shenzhen Yongjixing), USB ID `0edc:2050`
"YJXU502S USB Camera", Realtek UVC bridge.
- OV5648 1/4", 1.4 um pixels, max 2592x1944, MJPEG 30 fps / YUYV 15 fps at UXGA (1600x1200)
- Lens 72 deg fixed focus, PCB 1.2 mm, board 49.8 mm long, 9 mm wide, lens block 8.5 x 8.5 mm, 5.85 mm high
- 5 V, 140 mA. **Working temperature -20..70 C** (storage 0..50 C) - at the limit in a 70-80 C chamber
- **Connector 5P 1.0 mm: 1 VDD, 2 D-, 3 D+, 4 GND, 5 shield ground.** There is no LED pin.
- Microphone on the board (spec: "audio input supported")

**LED:** a single 3020 SMD white LED on the board (6000-7000 K, VF 2.8-3.4 V @ 20 mA, 30 mA max,
7-9 lm, 120 deg). It is driven by the camera chip's firmware, not by a separate circuit. ~8 lm is only a
fill/indicator light at close range; the chamber light remains Daylight on a stick.

**Firmware (this is what decides the LED):**
| Package | Version | LED behaviour | Notes |
|---|---|---|---|
| `YJX_OV5648_20181206_V100 (Continuous flash)` | V100, 2018-12-06 | LED on continuously | "initial version"; firmware has no "Realtek USB2.0 MIC" string -> microphone may be missing |
| `YJX_OV5648_20190415_V107 (Camera flash)` | V107, 2019-04-15 | LED flashes on still capture ("拍照闪灯", added in V101) | V104 shading + low-light compensation, V105-V107 mic volume max + sound tuning |

**Installed now: V107** (`bcdDevice 1.07`, serial string `20190415`). Still capture method 2 with
hardware trigger support is in the descriptors, so the LED only lights for a still-photo trigger.
Both `.rfw` files are kept in `~/camera_docs/vendor_20261124/fw_V100` and `fw_V107` (V107 = way back).

Flashing (vendor procedure): Windows only, run `UvcCamDownload_AllInOne_RsProxy.exe` from the package with
the camera plugged in, START, wait for green PASS; if it fails, replug and repeat.

## LED

Options after the vendor documents (2026-11-24):
1. Flash V100 "Continuous flash" -> LED always on, but likely loses the microphone and the V104 image
   tuning. Test on the Windows laptop, check LED + mic, flash V107 back if the mic is gone.
2. Hardware: lift the LED's drive from the chip and feed it from 5 V via resistor + MOSFET on a free MCU pin
   (one 3020 LED: ~100 ohm from 5 V for ~20 mA), `[output_pin camera_led]`.

Earlier research (2026-11-17), still valid:

- The only vendor control is UVC extension unit 4, GUID `{1229a78c-47b4-4094-b0ce-db07386fb938}`. It is a
  generic Realtek raw register access unit (same GUID/layout on HP laptop webcams with no LED), not an LED
  switch. Writing to it can brick the camera - never do it.
  Sources: https://www.mail-archive.com/linux-media@vger.kernel.org/msg133437.html ,
  https://forum.allaboutcircuits.com/threads/need-schematic-for-an-elp-camera.172639/post-1549249
- No v4l2 control, no vendor software, cameractrls/guvcview have no mapping for this GUID.
- Similar ELP/UICPAL boards power the LED ring from the camera's 5 V with their own small driver, sometimes
  with a light sensor (LDR) that switches it automatically.

**Hardware plan:**
1. Open the camera, find the 2-3 wires/traces to the LED ring, measure voltage (5 V or ~3 V) and current
   (estimate 20-150 mA).
2. Cut/unplug the LED + supply and feed it from 5 V through a logic-level MOSFET (AO3400 / 2N7000 or a
   ready MOSFET module), common ground with the camera.
3. Gate from a free MCU pin: `[output_pin camera_led]` with `pwm: True` (dimmable) and a Mainsail switch.
4. If there is an LDR on the ring, bypass it or keep it powered.

## Ideas (later)
- Speech boost in the go2rtc audio chain: `highpass` (keep it <= 60 Hz if the belt-tension measurement uses the
  same stream), `acompressor`, `volume` +10-15 dB. Mic gain is already at max (+12 dB, saved with alsactl).
- Belt tension by sound (see README TODO): FFT of a plucked belt, target ~110 Hz / 150 mm span on a V2.4.
