#!/bin/bash
# x-copy-chunked.sh v2 — 分块复制 staging 归档到 X 盘（绕 WSL 9p 大文件写失败）
# v2 2026-11-25: 修尾块死循环（剩余不足 1MB 时 mb=0 会原地打转），mb=0 直接跳出转 tail 补尾
set -uo pipefail
SRC="${1:?src}"
DST=/mnt/x/openclaw-backups/$(basename "$SRC")
LOG=/home/j/.openclaw/workspace/state/work/x-copy-run.log
say(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
S=$(stat -c%s "$SRC"); say "start src=$SRC size=$S dst=$DST"
rm -f "$DST.part"
CH=$((10*1024*1024*1024))
off=0
while [ "$off" -lt "$S" ]; do
  n=$(( S - off )); [ "$n" -gt "$CH" ] && n=$CH
  mb=$((n/1048576))
  [ "$mb" -le 0 ] && break
  dd if="$SRC" of="$DST.part" bs=1M skip=$((off/1048576)) seek=$((off/1048576)) count=$mb conv=notrunc,fsync status=none || { say "chunk fail at off=$off"; exit 1; }
  off=$(( off + mb*1048576 ))
  say "progress $off / $S"
done
rem=$(( S - off ))
if [ "$rem" -gt 0 ]; then tail -c "$rem" "$SRC" >> "$DST.part"; sync; say "tail $rem bytes appended"; fi
DS=$(stat -c%s "$DST.part" 2>/dev/null || echo 0)
if [ "$DS" = "$S" ]; then mv "$DST.part" "$DST"; sync; say "OK size match $DS"; else say "SIZE MISMATCH src=$S dst=$DS"; exit 2; fi
