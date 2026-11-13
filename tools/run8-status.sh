#!/usr/bin/env bash
export PATH="$HOME/.npm-global/bin:/usr/bin:/bin"
OC="$HOME/.npm-global/bin/openclaw"
out=/home/j/.openclaw/workspace/state/work/run8-status.txt
: > "$out"
while read -r line; do
  short=${line%% -> *}; full=${line##* -> }
  j=$("$OC" cron runs "$full" --limit 1 --json 2>/dev/null)
  st=$(printf "%s" "$j" | python3 -c "import json,sys;d=json.load(sys.stdin);r=(d.get('runs') or [{}])[0];print((r.get('status') or '?'), (r.get('startedAt') or ''), (r.get('error') or '')[:60])" 2>/dev/null || echo PARSE_ERR)
  echo "$short $st" >> "$out"
done < /tmp/st8.txt
echo DONE >> "$out"
