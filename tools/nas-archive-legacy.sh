#!/bin/bash
# nas-archive-legacy.sh v2 —— H 盘孤本归档到 NAS
# v1 教训：rsync 读 9p 大块报 Cannot allocate memory；改用 dd 1M 小块 + skip/seek 断点续传
set -uo pipefail
SRC=/mnt/h/openclaw-backups
DST=/mnt/nas/archive/legacy-20261031
LOG=/home/j/.openclaw/workspace/state/nas-archive-legacy.log
RES=/home/j/.openclaw/workspace/state/nas-archive-legacy.result
mkdir -p "$DST"
log(){ printf "%s %s\n" "$(date "+%F %T")" "$*" | tee -a "$LOG"; }
FILES=("2026-10-24T01-01-05.585+08-00-openclaw-backup.tar.gz" "2026-10-23T14-25-28.262+08-00-openclaw-backup.tar.gz" "2026-10-23T10-45-31.795+08-00-openclaw-backup.tar.gz" "2026-10-21T01-01-16.303+08-00-openclaw-backup.tar.gz" "2026-10-20T01-01-09.152+08-00-openclaw-backup.tar.gz" "2026-10-19T06-05-56.111+08-00-openclaw-backup.tar.gz" "2026-10-18T14-01-45.078+08-00-openclaw-backup.tar.gz" "2026-10-18T13-09-20.879+08-00-openclaw-backup.tar.gz" "2026-10-18T01-00-14.719+08-00-openclaw-backup.tar.gz")
FAIL=0
for b in "${FILES[@]}"; do
  s="$SRC/$b"; d="$DST/$b"
  [ -f "$s" ] || { log "MISS $b"; FAIL=1; continue; }
  sz=$(stat -c %s "$s")
  # 已校验过则跳过
  if [ -f "$d.sha256" ] && [ "$(stat -c %s "$d" 2>/dev/null || echo 0)" = "$sz" ]; then
    log "SKIP $b 已归档校验"; continue
  fi
  for try in 1 2 3 4 5; do
    cur=$(stat -c %s "$d" 2>/dev/null || echo 0)
    [ "$cur" -ge "$sz" ] && break
    skip=$(( cur / 1048576 ))
    log "COPY $b 第${try}次 从 $((skip))MB 处继续 (目标 ${cur}B)"
    dd if="$s" of="$d" bs=1M skip=$skip seek=$skip conv=notrunc 2>>"$LOG" || log "  dd 返回非零，重试"
  done
  cur=$(stat -c %s "$d" 2>/dev/null || echo 0)
  if [ "$cur" != "$sz" ]; then log "FAIL 大小不符 $b ($cur/$sz)"; FAIL=1; continue; fi
  log "HASH $b 计算中"
  h1=$(sha256sum "$s" | cut -d" " -f1)
  h2=$(sha256sum "$d" | cut -d" " -f1)
  if [ "$h1" = "$h2" ]; then
    printf "%s  %s\n" "$h2" "$b" > "$d.sha256"
    log "OK $b $h2"
  else
    log "FAIL 哈希不符 $b src=$h1 dst=$h2"; FAIL=1
  fi
done
if [ "$FAIL" = 0 ]; then echo "RESULT=ALL_OK" > "$RES"; log "DONE 全部归档校验通过，可删本地"; else echo "RESULT=FAIL" > "$RES"; log "DONE 有失败项，禁止删本地"; fi
