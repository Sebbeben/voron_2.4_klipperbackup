#!/usr/bin/env bash
# Moonraker database backup (print history, Mainsail settings).
# 1) Ask Moonraker for a consistent SQLite snapshot (refused while printing)
# 2) Push it to GitHub together with the config via klipper-backup
# Run by moonraker-db-backup.timer (systemd).
set -u
if curl -sf -X POST "http://localhost:7125/server/database/backup?filename=moonraker-db.sqlite" >/dev/null; then
    "$HOME/klipper-backup/script.sh" -c "Moonraker database backup $(date +%F)"
else
    echo "Moonraker database backup skipped (printer busy or Moonraker not running)"
fi
