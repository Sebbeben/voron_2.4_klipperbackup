# USB camera: audio + LED

Camera: "UICPAL" OV5648 5 MP AF, USB 0edc:2050, iManufacturer `YJXU502S`, Realtek RTS58xx bridge.
Video via crowsnest `[cam 2]` (ustreamer, port 8081, 1920x1080 @ 15). Microphone = ALSA card `Camera`
(`plughw:CARD=Camera,DEV=0`), works, about -37 dBFS with the fans running.

Status 2026-11-18: **go2rtc v1.9.14 installed and running** as systemd service `go2rtc` (unit file copy in
`system/go2rtc.service`). Video is H.264 1280x720 via an `exec:` ffmpeg command, because go2rtc 1.9.14
rejects the Bullseye ffmpeg 4.3 for `ffmpeg:` sources ("unsupported version"). Internal RTSP on
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
  URL `http://192.168.0.7:1984/api/webrtc?src=usbcam`, `extra_data.enableAudio: true`.
- Mainsail v2.19 creates the go2rtc `<video>` muted and without controls, so the sound could never be
  turned on. `system/mainsail_go2rtc_audio_patch.sh` adds `controls` to the player (video still autoplays
  muted; click the speaker icon). **Re-run the script after every Mainsail update**, then reload the
  browser with the cache cleared (service worker).
- The URL uses the LAN IP: over WireGuard use the go2rtc page via 10.0.0.9:1984 instead (or add an nginx
  proxy for go2rtc later).

### Ubuntu later (same support)

go2rtc is a single binary for amd64 as well (`go2rtc_linux_amd64`). On a PC the camera is not shared with
ustreamer, so use the device directly in the stream, e.g.
`ffmpeg:device?video=/dev/v4l/by-id/usb-YJXU502S_USB_Camera_20190415-video-index0#video=h264`
plus the same `exec:ffmpeg -f alsa ... plughw:CARD=Camera,DEV=0 ...` audio line. Desktop apps (Cheese,
OBS, guvcview) see the camera (UVC) and the microphone (USB Audio) without any driver.

## LED

**Not controllable from software** (web research 2026-11-17):

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
