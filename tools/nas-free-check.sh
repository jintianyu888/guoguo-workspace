#!/bin/bash
# nas-free-check.sh —— 群晖容量巡检（只读；<10% 告警）2026-10-23
set -uo pipefail
W=/home/j/.openclaw/workspace
NAS=nas
SSHN="ssh -o BatchMode=yes -o ConnectTimeout=15"
OUT=$(timeout 60 $SSHN "$NAS" "df -P /volume1 | tail -1" 2>/dev/null | tr -d "\r")
if [ -z "$OUT" ]; then echo "⚠️ 群晖不可达（ssh 失败）"; exit 1; fi
read -r fs tot used avail pct mnt <<< "$OUT"
pctn=${pct%\%}
echo "群晖 $mnt 已用 $pct（可用 ${avail}K）"
if [ "${pctn:-100}" -ge 90 ]; then
  bash "$W/tools/notify.sh" "🔴 群晖空间告急：$pct 已用（$mnt），可用 ${avail}K" >/dev/null 2>&1 || true
  exit 2
fi
exit 0

