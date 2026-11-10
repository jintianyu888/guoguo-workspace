#!/bin/bash
# migrate-workspaces-copy.sh —— E→X 工作区搬迁：阶段 1 复制+核对（不停服务、不动源）
set -uo pipefail
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
SRC=/home/j/openclaw-workspaces
DST=/home/j/openclaw-workspaces
LOG=/home/j/.openclaw/workspace/state/work/migrate-workspaces.log
say(){ echo "[$(date "+%F %T")] $*" | tee -a "$LOG"; }
mkdir -p "$DST"
say "阶段1开始：$SRC -> $DST"
rsync -a --info=stats2 --no-inc-recursive "$SRC/" "$DST/" >>"$LOG" 2>&1
RC=$?; say "rsync rc=$RC"
BAD=0; REPORT=/home/j/.openclaw/workspace/state/work/migrate-workspaces-verify.txt
: > "$REPORT"
for d in $(ls -1 "$SRC"); do
  [ -d "$SRC/$d" ] || continue
  a=$(find "$SRC/$d" -type f 2>/dev/null | wc -l); b=$(find "$DST/$d" -type f 2>/dev/null | wc -l)
  sa=$(du -sm "$SRC/$d" 2>/dev/null | cut -f1); sb=$(du -sm "$DST/$d" 2>/dev/null | cut -f1)
  st=OK; if [ "$a" != "$b" ] || [ "$sa" != "$sb" ]; then st=MISMATCH; BAD=$((BAD+1)); fi
  echo "$st $d files $a/$b MB $sa/$sb" >> "$REPORT"
done
M1=$(md5sum "$SRC/print/索引.md" 2>/dev/null | cut -d" " -f1); M2=$(md5sum "$DST/print/索引.md" 2>/dev/null | cut -d" " -f1)
[ "$M1" = "$M2" ] && echo "IDX OK $M1" >> "$REPORT" || { echo "IDX MISMATCH $M1 vs $M2" >> "$REPORT"; BAD=$((BAD+1)); }
say "核对完成：mismatch=$BAD（明细 $REPORT）"
timeout 90 bash /home/j/.openclaw/workspace/tools/notify.sh "📦 工作区复制完成：rsync rc=$RC，核对差异 $BAD 项。明细 state/work/migrate-workspaces-verify.txt" >/dev/null 2>&1 || true
exit 0