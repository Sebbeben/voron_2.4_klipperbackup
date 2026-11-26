#!/bin/bash
# TMC2209 uv_cp isolation test WITHOUT motion (2026-11-26).
# Repeatedly switches one driver at standstill to the register set Klipper uses for
# sensorless homing (stealthChop: tpwmthrs 0 / en_spreadcycle 0, tcoolthrs max, homing
# current) and back. A healthy driver never reports GSTAT uv_cp here.
# Usage: uv_cp_test.sh STEPPER [CYCLES=20] [HOME_CURRENT=0.49] [RUN_CURRENT=0.8]
P='localhost:7125/printer/gcode/script'
g(){ curl -s -m 30 -X POST $P -H 'Content-Type: application/json' -d "{\"script\":\"$1\"}" >/dev/null; }
st(){ curl -s localhost:7125/printer/info | python3 -c "import json,sys;r=json.load(sys.stdin)['result'];print(r['state'],r['state_message'].splitlines()[0][:90])"; }
S=$1; N=${2:-20}; H=${3:-0.49}; R=${4:-0.8}
if [[ "$(st)" != ready* ]]; then curl -s -X POST localhost:7125/printer/firmware_restart >/dev/null; sleep 15; fi
g "SET_STEPPER_ENABLE STEPPER=$S ENABLE=1"
for i in $(seq 1 "$N"); do
  g "SET_TMC_CURRENT STEPPER=$S CURRENT=$H\nG4 P1000\nSET_TMC_FIELD STEPPER=$S FIELD=tpwmthrs VALUE=0\nSET_TMC_FIELD STEPPER=$S FIELD=en_spreadcycle VALUE=0\nSET_TMC_FIELD STEPPER=$S FIELD=tcoolthrs VALUE=1048575\nG4 P1500\nSET_TMC_FIELD STEPPER=$S FIELD=tcoolthrs VALUE=0\nSET_TMC_FIELD STEPPER=$S FIELD=en_spreadcycle VALUE=1\nSET_TMC_FIELD STEPPER=$S FIELD=tpwmthrs VALUE=1048575\nSET_TMC_CURRENT STEPPER=$S CURRENT=$R\nG4 P1000"
  s=$(st); if [[ "$s" != ready* ]]; then echo "$S: FAIL on cycle $i: $s"; exit 1; fi
done
g "M84"; echo "$S: $N/$N OK"
