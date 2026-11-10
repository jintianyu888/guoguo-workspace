#!/bin/bash
# av-scan.sh — ClamAV 定时扫描（每周），只输出一行结论（干净/发现）
W=/home/j/.openclaw/workspace
LOG=$W/state/work/av-scan.log
OUT=$(mktemp)
mkdir -p "$W/state/work"
# 2026-10-20 堵假绿：clamscan 缺失/rc≠0/空统计时曾报「🟢无感染（）」给飞书
date "+== %F %T AV扫描开始" >> "$LOG"
if ! command -v clamscan >/dev/null 2>&1; then
  echo "🔴 AV扫描：clamscan 未安装！本次未扫描（引擎缺失≠干净），详见 [54] 督察"
  exit 1
fi
# 2026-10-21 提速：跳过不可执行的大体积二进制目录 + 单文件/扫描体积上限（原 600s 内跑不完）
clamscan -r --infected \
  --exclude-dir='node_modules' --exclude-dir='\.git' --exclude-dir='venvs' \
  --exclude-dir='tools/models' --exclude-dir='tools/asr-venv' --exclude-dir='tools/ocr-venv' \
  --exclude-dir='tools/embed-venv' --exclude-dir='tools/py-tts' --exclude-dir='tools/lo' \
  --exclude-dir='\.dead' --exclude-dir='backup-extra' --exclude-dir='state/dl' \
  --exclude-dir='state/tmp' --exclude-dir='state/work' --exclude-dir='_trash' \
  --max-filesize=100M --max-scansize=400M \
  "$W" > "$OUT" 2>&1
RC_CLAM=$?
INF=$(grep -c 'FOUND' "$OUT")
SCANNED=$(grep -oE 'Scanned files: [0-9]+' "$OUT" | head -1)
cat "$OUT" >> "$LOG"
if [ "$RC_CLAM" -ne 0 ]; then
  echo "🔴 AV扫描：clamscan 退出码 $RC_CLAM（扫描异常，勿当作干净）"
  grep -iE 'error|warn' "$OUT" | head -5
  # 2026-10-27 审查#2：异常分支不再删日志，留存供排查
  cp -f "$OUT" "$W/state/work/av-scan-failed-$(date +%Y%m%d-%H%M%S).txt" 2>/dev/null
  rm -f "$OUT"
  exit 1
fi
if [ -z "$SCANNED" ]; then
  echo "🔴 AV扫描：无统计产出（疑似未真扫），详见 $LOG"
  # 2026-10-27 审查#3：无统计时同样留存输出，便于复查
  cp -f "$OUT" "$W/state/work/av-scan-nostats-$(date +%Y%m%d-%H%M%S).txt" 2>/dev/null
  rm -f "$OUT"
  exit 1
fi
if [ "$INF" -gt 0 ]; then
  echo "🔴 AV扫描：发现 $INF 个可疑文件！"
  grep 'FOUND' "$OUT" | head -10
else
  echo "🟢 AV扫描：无感染（$SCANNED；已跳过 models/venv 等大目录）"
fi
rm -f "$OUT"
