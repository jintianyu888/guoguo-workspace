#!/usr/bin/env bash
set -u
export PATH="$HOME/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
OC="$HOME/.npm-global/bin/openclaw"
W=/home/j/.openclaw/workspace
LOG=$W/state/work/run8-rest.log
: > "$LOG"
for id in 564aeb60-60c4-4e9f-92cb-654c4f579d4a 2fd10b3c-1882-4789-8ec1-3f1f7d41bba4 330261ca-5dcf-42fc-b2a1-c625a5cf4f69 6ec8ec62-442a-4372-a146-05300d0da962 935c9c9e-a99c-480c-bb4f-e53b0389c7df aeeb49c3-471b-4474-b2e1-dd2883fc7394; do
  timeout 600 "$OC" cron run "$id" --json >> "$LOG" 2>&1 &
  echo "fired $id" >> "$LOG"
  sleep 3
done
wait
echo "FIRE_ALL_DONE" >> "$LOG"
