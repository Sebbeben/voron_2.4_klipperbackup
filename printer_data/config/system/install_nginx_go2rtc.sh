#!/bin/bash
# Proxy go2rtc through the Mainsail nginx at /go2rtc/ so the webcam works from any address
# (LAN 192.168.0.x and WireGuard 10.0.0.9) and the WebSocket origin check in go2rtc passes.
# Run with: sudo bash ~/printer_data/config/system/install_nginx_go2rtc.sh
set -e
f=/etc/nginx/sites-available/mainsail
grep -q 'location /go2rtc/' "$f" && { echo "already installed"; exit 0; }
cp "$f" "$f.before_go2rtc"
python3 - "$f" <<'PY'
import sys
p=sys.argv[1]; s=open(p).read()
block='''    location /go2rtc/ {
        proxy_pass http://127.0.0.1:1984/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $http_host;
        proxy_read_timeout 86400;
    }

'''
anchor='    location /webcam/ {'
assert s.count(anchor)==1, 'anchor not found'
open(p,'w').write(s.replace(anchor, block+anchor))
PY
nginx -t && systemctl reload nginx && echo "nginx reloaded, go2rtc at /go2rtc/"
