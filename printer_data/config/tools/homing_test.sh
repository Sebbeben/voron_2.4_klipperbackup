#!/bin/bash
# Repeated X/Y homing test via Moonraker (used to hunt the motor B uv_cp fault).
# Usage: homing_test.sh [cycles=10]
# Stops at the first Klipper shutdown/error and prints the reason.
# Run only with someone watching the printer.
N=${1:-10}
API=http://localhost:7125
gc() { curl -s -m 120 -X POST "$API/printer/gcode/script" -H 'Content-Type: application/json' -d "{\"script\": \"$1\"}"; }
state() { curl -s "$API/printer/info" | python3 -c 'import json,sys;r=json.load(sys.stdin)["result"];print(r["state"]+"|"+r["state_message"].splitlines()[0])'; }
ok=0
for i in $(seq 1 "$N"); do
  r=$(gc "G28 X Y")
  s=$(state)
  if [[ "$s" != ready* ]] || echo "$r" | grep -q '"error"'; then
    echo "#$i FAILED: $s"; echo "$r" | head -c 400; echo; break
  fi
  ok=$((ok+1)); echo "#$i OK"
  gc "G90\nG1 X175 Y175 F6000" >/dev/null
done
echo "$ok/$N homing cycles OK"
