#!/bin/bash
# Adds browser player controls (incl. the speaker/unmute button) to Mainsail's go2rtc WebRTC webcam player.
# Mainsail v2.19 creates the <video> muted and without controls, so "Enable audio" can never be heard.
# The video still autoplays muted (browsers block autoplay with sound); click the speaker icon to listen.
# Re-run after every Mainsail update (the update replaces the file). Browser: reload with cache cleared
# (Mainsail's service worker caches the old file).
set -e
cd ~/mainsail/assets
f=$(ls WebrtcGo2rtc-*.js)
old='attrs:{autoplay:``,playsinline:``,muted:``},domProps:{muted:!0}'
new='attrs:{autoplay:``,playsinline:``,muted:``,controls:``},domProps:{muted:!0}'
if grep -qF "$new" "$f"; then echo "already patched: $f"; exit 0; fi
grep -qF "$old" "$f" || { echo "pattern not found in $f (Mainsail changed?) - not patched"; exit 1; }
cp "$f" "$f.orig"
sed -i "s/$(printf '%s' "$old" | sed 's/[]\/$*.^[]/\\&/g')/$(printf '%s' "$new" | sed 's/[]\/$*.^[&]/\\&/g')/" "$f"
grep -qF "$new" "$f" && echo "patched: $f"
