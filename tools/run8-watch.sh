#!/usr/bin/env bash
set -u
export PATH="$HOME/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
W=/home/j/.openclaw/workspace
OUT=$W/state/work/run8-final.txt
for i in $(seq 1 75); do
  python3 -u "$W/tools/run8-check.py" > "$OUT" 2>&1
  pend=$(grep -c "今日无新运行记录" "$OUT" || true)
  echo "$(date +%T) pending=$pend" >> "$W/state/work/run8-watch.log"
  if [ "$pend" -eq 0 ]; then break; fi
  sleep 60
done
MSG="【8 个补跑任务汇总】"
MSG="$MSG$(printf "\n")$(cat "$OUT")"
bash "$W/tools/notify.sh" "$MSG" >/dev/null 2>&1 || true
echo DONE >> "$W/state/work/run8-watch.log"
