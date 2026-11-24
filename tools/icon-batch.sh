#!/bin/bash
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/icons/batch2.log
: > "$LOG"
PAIRS="
cli_aa5dea961cf89bb3 info
cli_aa413becfd78dbdf security
cli_aa57e36b35f8dd2e law
cli_aa3dced661b85bb7 gege
cli_aa34f85e0a38dbd7 health
cli_aa35c97bfff89be3 health-doudou
cli_aa34f8dbcb785bd9 health-wife
cli_aa258581da785cb5 health-mom
cli_aa5dea81f2f81c07 company1
cli_aa5deabef73bdbb4 company2
cli_aa5deab785789c0c company3
cli_aa34942fd238dbb3 paike
cli_aa5dea5fd0b85bb0 agant
cli_aa5dea9c70b91c06 work
cli_aa3d74c505b8dbe0 hermess
"
echo "START $(date +%H:%M:%S)" >> "$LOG"
echo "$PAIRS" | while read -r id key; do
  [ -z "$id" ] && continue
  echo "== $key $id $(date +%H:%M:%S)" >> "$LOG"
  timeout 200 node "$W/tools/icon-apply.js" "$id" "$W/state/icons/new/$key.png" "更新应用图标：$key" >> "$LOG" 2>&1
  echo "  rc=$? $(date +%H:%M:%S)" >> "$LOG"
  sleep 2
done
echo "DONE $(date +%H:%M:%S)" >> "$LOG"
