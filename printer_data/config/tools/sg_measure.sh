#!/bin/bash
# Measure TMC2209 StallGuard4 SG_RESULT while moving, in the same mode Klipper uses for
# sensorless homing (stealthChop: en_spreadcycle 0 + tpwmthrs 0, homing current). 2026-11-26.
# The toolhead must stand near the centre: it is set to X175 Y175 and moves +-50 mm on AXIS.
# Usage: sg_measure.sh AXIS(X|Y) [CURRENT=0.49] [SPEED_MMS=80]
# Stall triggers when SG_RESULT <= 2 * SGTHRS -> pick SGTHRS well below min/2.
P='localhost:7125/printer/gcode/script'
g(){ curl -s -m 60 -X POST $P -H 'Content-Type: application/json' -d "{\"script\":\"$1\"}" >/dev/null; }
A=$1; C=${2:-0.49}; V=${3:-80}; F=$(( V * 60 )); S=stepper_$(echo $A | tr XY xy)
RUN=$(curl -s "localhost:7125/printer/objects/query?configfile=settings" | python3 -c "import json,sys;print(json.load(sys.stdin)['result']['status']['configfile']['settings']['tmc2209 $S']['run_current'])")
on="";off=""
for s in stepper_x stepper_y; do
  on="$on\nSET_TMC_CURRENT STEPPER=$s CURRENT=$C\nSET_TMC_FIELD STEPPER=$s FIELD=en_spreadcycle VALUE=0\nSET_TMC_FIELD STEPPER=$s FIELD=tpwmthrs VALUE=0"
  off="$off\nSET_TMC_FIELD STEPPER=$s FIELD=en_spreadcycle VALUE=1\nSET_TMC_FIELD STEPPER=$s FIELD=tpwmthrs VALUE=1048575\nSET_TMC_CURRENT STEPPER=$s CURRENT=$RUN"
done
g "SET_KINEMATIC_POSITION X=175 Y=175 SET_HOMED=xy$on\nG90\nG1 ${A}125 F3000\nG4 P1000\nM400"
T0=$(date +%s.%N)
g "G1 ${A}225 F$F\nG1 ${A}125 F$F\nG1 ${A}225 F$F\nG1 ${A}125 F$F\nG1 ${A}225 F$F\nG1 ${A}125 F$F"
for i in $(seq 1 40); do g "DUMP_TMC STEPPER=$S REGISTER=SG_RESULT"; done
g "M400\nG1 ${A}175 F3000\nM400$off\nM84"
curl -s "localhost:7125/server/gcode_store?count=300" | python3 -c "
import json,sys,re
v=[int(m.group(1)) for g in json.load(sys.stdin)['result']['gcode_store'] if g['time']>=$T0 for m in [re.search(r'sg_result=(\d+)',g['message'])] if m]
mv=[x for x in v if x!=v[-1]] or v   # drop the stale standstill value
print('$A ($S) $C A $V mm/s: moving n=%d min=%d median=%d max=%d' % (len(mv),min(mv),sorted(mv)[len(mv)//2],max(mv)))"
