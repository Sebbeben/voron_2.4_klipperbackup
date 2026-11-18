#!/bin/bash
# Adds browser player controls (incl. the speaker/unmute button) to Mainsail's go2rtc WebRTC webcam player.
# Mainsail v2.19 creates the <video> muted and without controls, so "Enable audio" can never be heard.
# The video still autoplays muted (browsers block autoplay with sound); click the speaker icon to listen.
# Also: controlsList hides download/speed/cast, PiP disabled; .theme/custom.css hides play/pause + timeline.
# Re-run after every Mainsail update (the update replaces the file). Browser: reload with cache cleared
# (Mainsail's service worker caches the old file).
set -e
cd ~/mainsail/assets
f=$(ls WebrtcGo2rtc-*.js)
old='attrs:{autoplay:``,playsinline:``,muted:``},domProps:{muted:!0}'
new='attrs:{autoplay:``,playsinline:``,muted:``,controls:``,controlslist:`nodownload noplaybackrate noremoteplayback`,disablepictureinpicture:``},domProps:{muted:!0}'
if grep -qF "$new" "$f"; then echo "already patched: $f"; exit 0; fi
# earlier version of this patch (controls only) -> start again from the original file
[ -f "$f.orig" ] && cp "$f.orig" "$f"
grep -qF "$old" "$f" || { echo "pattern not found in $f (Mainsail changed?) - not patched"; exit 1; }
[ -f "$f.orig" ] || cp "$f" "$f.orig"
sed -i "s/$(printf '%s' "$old" | sed 's/[]\/$*.^[]/\\&/g')/$(printf '%s' "$new" | sed 's/[]\/$*.^[&]/\\&/g')/" "$f"
grep -qF "$new" "$f" && echo "patched: $f"
