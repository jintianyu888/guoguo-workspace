#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "需用 bash 运行: bash $0" >&2; exit 1; }
python3 /home/j/.openclaw/workspace/tools/quiet_window.py >/dev/null 2>&1 && exit 0
# proc-watch.sh v3 —— 进程体检（只报真·卡住；同一状态只在"出现/解除"时报一次，绝不复读）
W=/home/j/.openclaw/workspace; S=$W/state/.procwatch; mkdir -p "$S"
ISSUE=""
# ① 僵尸（排除内核线程）
Z=$(ps -eo stat=,pid=,comm= --no-headers 2>/dev/null | awk '$1 ~ /^Z/' | head -3)
[ -n "$Z" ] && ISSUE="${ISSUE}僵尸进程:$(echo "$Z" | awk '{print $2}' | tr '\n' ' ')"
# ② D 状态（IO 卡死）—— 交给分类器判定：9p/Windows 盘等待、上下文切换仍在推进的进程不算卡死（2026-10-17 根因修复）
D=$(python3 "$W/tools/io-stuck-watch.py" --json --alert-seconds 180 2>/dev/null | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    print(" ".join(str(a.get("pid")) for a in d.get("alerts", [])))
except Exception:
    pass')
[ -n "$D" ] && ISSUE="${ISSUE} IO卡死:$D"
# ③ 卡住的同步（ssh/scp/rsync 超 30 分钟）
SY=""
while read -r et pid comm; do
  case "$comm" in ssh|scp|rsync|sftp) m=${et##*:}; m=${m%%:*}; [ "${m:-0}" -ge 30 ] 2>/dev/null && SY="$SY $pid";; esac
done < <(ps -eo etime=,pid=,comm= --no-headers 2>/dev/null)
[ -n "$SY" ] && ISSUE="${ISSUE} 同步卡住>30分:$SY"
# ④ 去重：状态没变 → 一个字不发
LF=$S/last; LAST=""; [ -f "$LF" ] && LAST=$(cat "$LF")
[ "$ISSUE" = "$LAST" ] && exit 0
printf '%s' "$ISSUE" > "$LF"
if [ -n "$ISSUE" ] && [ -z "$LAST" ]; then
  echo "🩺 进程体检（$(date '+%m-%d %H:%M')）发现：${ISSUE}"
  echo "—— 怎么办：卡住的同步我直接杀；僵尸/D 状态我清；处理不了才找你。"
elif [ -z "$ISSUE" ] && [ -n "$LAST" ]; then
  echo "✅ 进程体检已解除（之前：${LAST}）"
fi
# 同状态重复出现时：静默（exit 0）