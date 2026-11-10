#!/bin/bash
# verify-then-prune v3 (2026-10-18 主公令)：删除必须「文件名+大小+SHA256」三项全一致
set -u
# 2026-10-18 补丁A（GLM 评审）：并发互斥
_LK=/home/j/.openclaw/workspace/state/work/verify-then-prune.lock
mkdir -p "$(dirname "$_LK")"
exec 9>"$_LK"
flock -n 9 || { echo "SKIP 已有 verify-then-prune 实例在跑"; exit 0; }
W=/home/j/.openclaw/workspace
LOG=$W/state/work/hash-verify.log
OUT=$W/state/work/hash-compare.md
LED=$W/state/backup-hash-ledger.jsonl
LH=$W/state/backups-hash
NAS=nas
RD=/var/services/homes/guoguonas/archive/jinyu/openclaw-archives
HD=/mnt/h/openclaw-backups
mkdir -p "$LH" "$W/state/work"
FILES=(
  2026-10-08T00-30-10.494+08-00-openclaw-backup.tar.gz
  2026-10-09T00-30-10.435+08-00-openclaw-backup.tar.gz
  2026-10-10T00-30-10.812+08-00-openclaw-backup.tar.gz
  2026-10-11T00-30-10.741+08-00-openclaw-backup.tar.gz
  2026-10-12T00-30-12.362+08-00-openclaw-backup.tar.gz
  2026-10-13T00-30-12.681+08-00-openclaw-backup.tar.gz
)
N=${#FILES[@]}
rq() { timeout 40 ssh -o BatchMode=yes -o ConnectTimeout=10 "$NAS" "$1" 2>/dev/null | tr -d "\r"; }
echo "=== $(date "+%F %T") v3 开始：三重校验（名+大小+SHA256），未批准不删 ===" >> "$LOG"

rq 'sh ~/hash-verify/nas-hash.sh' >> "$LOG" 2>&1 &
RPID=$!
i=0
for f in "${FILES[@]}"; do
  i=$((i+1)); o="$LH/$f.sha256"
  if [ -s "$o" ] && [ "$(cut -c1-64 "$o")" != "" ]; then echo "  本地缓存 $i/$N" >> "$LOG"; continue; fi
  echo "  本地 $i/$N 开始 $f" >> "$LOG"
  sha256sum "$HD/$f" > "$o.tmp" 2>>"$LOG" && mv "$o.tmp" "$o"
  echo "  本地 $i/$N 完成 $(cut -c1-16 "$o")" >> "$LOG"
done
wait $RPID; echo "  远端哈希结束 rc=$?" >> "$LOG"

echo "| 文件 | 大小(H/NAS) | SHA256(H) | SHA256(NAS) | 判定 |" > "$OUT"
echo "|---|---|---|---|---|" >> "$OUT"
for f in "${FILES[@]}"; do
  sl=$(stat -c %s "$HD/$f" 2>/dev/null || echo 0)
  sr=$(rq "stat -c %s $RD/$f 2>/dev/null" | head -1)
  lh=$(cut -c1-64 "$LH/$f.sha256" 2>/dev/null || true)
  nh=$(rq "cat ~/hash-verify/$f.sha256 2>/dev/null" | cut -c1-64)
  if [ -n "$lh" ] && [ "$lh" = "$nh" ] && [ -n "$sr" ] && [ "$sl" = "$sr" ]; then v="三项一致 ✅"; else v="不一致/缺 ⚠️"; fi
  echo "| $f | ${sl:0:12} / ${sr:0:12} | ${lh:0:16} | ${nh:0:16} | $v |" >> "$OUT"
  printf '{"ts":"%s","file":"%s","size_local":%s,"size_nas":%s,"sha_local":"%s","sha_nas":"%s","verdict":"%s"}' "$(date -Iseconds)" "$f" "${sl:-0}" "${sr:-0}" "$lh" "$nh" "$v" >> "$LED"; echo >> "$LED"
done
echo "=== $(date "+%F %T") 比对完成 ===" >> "$LOG"

if [ -f "$W/state/work/prune-approved" ]; then
  d=0
  for f in "${FILES[@]}"; do
    sl=$(stat -c %s "$HD/$f" 2>/dev/null || echo 0)
    sr=$(rq "stat -c %s $RD/$f 2>/dev/null" | head -1)
    lh=$(cut -c1-64 "$LH/$f.sha256" 2>/dev/null || true)
    nh=$(rq "cat ~/hash-verify/$f.sha256 2>/dev/null" | cut -c1-64)
    if [ -n "$lh" ] && [ "$lh" = "$nh" ] && [ -n "$sr" ] && [ "$sl" = "$sr" ]; then
      if rq "rm -f $RD/$f && echo GONE" | grep -q GONE; then
        echo "  DEL $f (名+大小+SHA256 三项一致)" >> "$LOG"; d=$((d+1))
      else echo "  WARN 删除失败 $f" >> "$LOG"; fi
    else echo "  KEEP 未过三重校验 $f" >> "$LOG"; fi
  done
  echo "  已批准：共删 $d 份" >> "$LOG"
else
  echo "  未批准（缺 state/work/prune-approved），一份未删" >> "$LOG"
fi