#!/bin/bash
# away-watch.sh —— 主公外出值守体检（零 token）。2026-11-25 立
set -uo pipefail
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
OUT=$W/state/work/away-watch-latest.md
TMP=$(mktemp); RED=0
add(){ echo "$1" >> "$TMP"; }
red(){ RED=1; echo "🔴 $1" >> "$TMP"; }

V=$(openclaw --version 2>/dev/null | tail -1)
H=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18789/health 2>/dev/null)
add "版本：$V"
if [ "$H" = "200" ]; then add "网关：health 200"; else red "网关 health=$H"; fi

RC=$(cd "$W" && timeout 240 python3 tools/rules-check.py 2>/dev/null | grep -c "❌" || true)
if [ "$RC" -gt 0 ]; then red "规则红灯 $RC 条"; else add "规则：全绿"; fi

JF=$(cd "$W" && timeout 120 python3 tools/job-ledger.py report 24 2>/dev/null | grep -oE "真失败 [0-9]+" | grep -oE "[0-9]+" | head -1)
JF=$(printf '%s' "$JF" | tr -dc '0-9')
if [ -z "$JF" ]; then JF=0; fi
if [ "$JF" -gt 5 ]; then red "定时任务 24h 真失败 $JF 次"; else add "定时任务：24h 真失败 $JF"; fi

SK=$(cd "$W" && timeout 120 python3 tools/stuck-watch.py 2>/dev/null | grep -c "🔴" || true)
if [ "$SK" -gt 0 ]; then red "卡住项 $SK 条"; else add "卡住：0"; fi

D=$(date +%F); CNT=0; MISS=""
for m in x d e h; do
  f=$(ls -1 /mnt/$m/openclaw-backups/"$D"T*openclaw-backup.tar.gz 2>/dev/null | head -1)
  if [ -n "$f" ]; then CNT=$((CNT+1)); else MISS="$MISS $m"; fi
done
n=$(ls -1 /mnt/nas/archive/jinyu/openclaw-archives/"$D"T*openclaw-backup.tar.gz 2>/dev/null | head -1)
if [ -n "$n" ]; then CNT=$((CNT+1)); else MISS="$MISS nas"; fi
if [ "$CNT" -lt 5 ]; then red "备份仅 $CNT/5 份（缺:$MISS）"; else add "备份：5/5 份齐（$D）"; fi

DR=$(df / | awk 'NR==2{gsub("%","",$5);print $5}')
if [ "$DR" -ge 85 ]; then red "根盘已用 $DR%"; else add "根盘：$DR%"; fi

{ echo "# 值守体检 $(date '+%F %T')"; echo; cat "$TMP"; } > "$OUT"
if [ "$RED" = "1" ]; then
  bash "$W/tools/notify.sh" "【值守体检】发现问题：$(grep '🔴' "$TMP" | tr '\n' ';')" >/dev/null 2>&1
  echo "RED $(grep -c '🔴' "$TMP")"; rm -f "$TMP"; exit 1
fi
echo "GREEN 全项通过"; rm -f "$TMP"
