#!/usr/bin/env python3
"""Belt tension by sound: record plucks with the USB camera microphone and report the
belt's fundamental frequency.

Usage:
    belt_freq.py [--seconds 8] [--fmin 60] [--fmax 250] [--wav file.wav] [--save out.wav]

Pluck the belt span 3-6 times while it records (about 1 s apart, same spot, same
strength). Voron 2.4 target: ~110 Hz on a 150 mm span (A and B belts within a few Hz).
The part fan and the Nevermore are switched off during the recording and restored
afterwards (--keep-fans to skip). Heater fans (hotend, controller) are never forced off:
measure with a cold printer. Keep the microphone close (move the camera if needed).

The microphone is ALSA card "Camera" (plughw:CARD=Camera,DEV=0). If go2rtc is streaming
audio at that moment the device is busy, and the script records from go2rtc's RTSP
stream instead (Opus, fine for 60-250 Hz).
"""
import argparse
import subprocess
import sys
import tempfile
import wave

import numpy as np

DEVICE = "plughw:CARD=Camera,DEV=0"
RATE = 16000
GO2RTC_AUDIO = "rtsp://127.0.0.1:8556/usbcam_audio"  # fallback when the ALSA device is busy


MOONRAKER = "http://localhost:7125"


def _api(path, script=None):
    import json
    import urllib.request
    if script is None:
        req = urllib.request.Request(MOONRAKER + path)
    else:
        req = urllib.request.Request(MOONRAKER + "/printer/gcode/script",
                                     data=json.dumps({"script": script}).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def fans_off():
    """Switch off the fans Klipper may switch off; return G-code that restores them.
    Heater-controlled fans (hotend, controller) are never forced off - only reported."""
    try:
        st = _api("/printer/objects/query?fan&fan_generic%20nevermore"
                  "&heater_fan%20hotend_fan&heater_fan%20controller_fan")["result"]["status"]
    except Exception as e:  # Klipper not running: just measure
        print(f"(could not read fans from Moonraker: {e})")
        return ""
    restore = []
    part = st.get("fan", {}).get("speed", 0) or 0
    if part > 0:
        _api(None, "M107")
        restore.append(f"M106 S{round(part * 255)}")
    nev = st.get("fan_generic nevermore", {}).get("speed", 0) or 0
    if nev > 0:
        _api(None, "SET_FAN_SPEED FAN=nevermore SPEED=0")
        restore.append(f"SET_FAN_SPEED FAN=nevermore SPEED={nev:.2f}")
    for name, why in (("heater_fan hotend_fan", "hotend > 50 C"), ("heater_fan controller_fan", "bed > 45 C")):
        if (st.get(name, {}).get("speed", 0) or 0) > 0:
            print(f"WARNING: {name.split()[1]} is running ({why}) and is left on - let it cool for a clean result")
    if restore:
        print("Fans off for the measurement: part fan / Nevermore")
    return "\n".join(restore)


def record(seconds, path):
    cmd = ["arecord", "-q", "-D", DEVICE, "-f", "S16_LE", "-c", "1", "-r", str(RATE),
           "-d", str(seconds), path]
    print(f"Recording {seconds} s - pluck the belt now ...", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        return
    # ALSA device busy (go2rtc is streaming the mic to a viewer): take the audio from go2rtc instead.
    print("ALSA busy (" + r.stderr.strip()[:80] + ") - recording via go2rtc RTSP instead", flush=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-rtsp_transport", "tcp",
           "-i", GO2RTC_AUDIO, "-t", str(seconds), "-vn", "-ac", "1", "-ar", str(RATE), path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("recording failed: " + r.stderr.strip())


def load(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            sys.exit("only 16-bit WAV supported")
        rate = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return data / 32768.0, rate


def find_plucks(x, rate, min_gap=0.4):
    """Onsets = frames whose short-time energy jumps well above the noise floor."""
    hop = int(rate * 0.01)
    n = len(x) // hop
    env = np.sqrt(np.array([np.mean(x[i * hop:(i + 1) * hop] ** 2) for i in range(n)]) + 1e-12)
    floor = np.median(env)
    thr = max(floor * 6, np.percentile(env, 99) * 0.25)
    onsets, last = [], -1e9
    for i in range(1, n):
        if env[i] > thr and env[i - 1] <= thr and (i - last) * hop / rate > min_gap:
            onsets.append(i * hop)
            last = i
    return onsets, 20 * np.log10(floor + 1e-12)


def peak_freq(seg, rate, fmin, fmax):
    seg = seg - seg.mean()
    seg = seg * np.hanning(len(seg))
    nfft = 1 << 17  # zero padding -> ~0.1 Hz bins at 16 kHz
    spec = np.abs(np.fft.rfft(seg, nfft))
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
    band = (freqs >= fmin) & (freqs <= fmax)
    i = np.argmax(spec[band])
    f = freqs[band][i]
    # strength of the peak vs the band median (rough confidence)
    snr = 20 * np.log10(spec[band][i] / (np.median(spec[band]) + 1e-12))
    return f, snr


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=int, default=8)
    ap.add_argument("--fmin", type=float, default=60.0)
    ap.add_argument("--fmax", type=float, default=250.0)
    ap.add_argument("--wav", help="analyse an existing 16-bit WAV instead of recording")
    ap.add_argument("--save", help="keep the recording as this WAV file")
    ap.add_argument("--keep-fans", action="store_true", help="do not switch the part fan / Nevermore off")
    a = ap.parse_args()

    if a.wav:
        path = a.wav
    else:
        path = a.save or tempfile.mktemp(suffix=".wav")
        restore = "" if a.keep_fans else fans_off()
        try:
            if restore:
                import time
                time.sleep(3)  # let the fans spin down
            record(a.seconds, path)
        finally:
            if restore:
                _api(None, restore)
                print("Fans restored")

    x, rate = load(path)
    onsets, floor_db = find_plucks(x, rate)
    print(f"noise floor {floor_db:.0f} dBFS, {len(onsets)} pluck(s) found")
    results = []
    for k, o in enumerate(onsets, 1):
        start = o + int(0.03 * rate)          # skip the click of the pluck itself
        seg = x[start:start + int(0.5 * rate)]
        if len(seg) < int(0.2 * rate):
            continue
        f, snr = peak_freq(seg, rate, a.fmin, a.fmax)
        flag = "" if snr >= 15 else "  (weak, ignored)"
        print(f"  pluck {k} at {o / rate:5.2f} s: {f:6.1f} Hz  peak {snr:4.1f} dB{flag}")
        if snr >= 15:
            results.append(f)
    if not results:
        f, snr = peak_freq(x, rate, a.fmin, a.fmax)
        print(f"No clear plucks. Whole-recording peak: {f:.1f} Hz ({snr:.1f} dB) - pluck harder / move the mic closer.")
        sys.exit(1)
    r = np.array(results)
    print(f"RESULT: {np.median(r):.1f} Hz (median of {len(r)}, spread {r.min():.1f}-{r.max():.1f} Hz)")


if __name__ == "__main__":
    main()
