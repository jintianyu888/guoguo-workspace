#!/bin/bash
# nas-seed-copy.sh v2 —— 种子拷贝（断点续传 + 重试 + 三重校验）
# v1 教训：cp 读 /mnt/e(9p) 报 "Cannot allocate memory"，改用 rsync --append-verify 小步重试
set -uo pipefail
SRC_DIR="${SRC_DIR:-/mnt/e/openclaw-backups}"
DST_DIR="${DST_DIR:-/mnt/nas/backup/openclaw/full}"
LOG="/home/j/.openclaw/workspace/state/nas-seed-copy.log"
RES="/home/j/.openclaw/workspace/state/nas-seed-copy.result"
mkdir -p "$DST_DIR"
log() { printf "%s %s\n" "$(date "+%F %T")" "$*" | tee -a "$LOG"; }
F="$(ls -1t "$SRC_DIR"/*.tar.gz 2>/dev/null | head -1)"
[ -z "$F" ] && { log "ERROR 找不到源备份"; echo "RESULT=NO_SRC" > "$RES"; exit 1; }
B="$(basename "$F")"
SZ="$(stat -c %s "$F")"
log "START $B size=$SZ"
if [ -f "$DST_DIR/$B.part" ]; then
  PSZ="$(stat -c %s "$DST_DIR/$B.part" 2>/dev/null || echo 0)"
  log "续传 已存在 part ${PSZ}B，重命名为目标后 append-verify"
  mv -f "$DST_DIR/$B.part" "$DST_DIR/$B"
fi
ATTEMPT=0
while [ "$ATTEMPT" -lt 3 ]; do
  ATTEMPT=$((ATTEMPT+1))
  CUR="$(stat -c %s "$DST_DIR/$B" 2>/dev/null || echo 0)"
  [ "$CUR" = "$SZ" ] && { log "大小已一致，跳过复制"; break; }
  log "COPY 第 $ATTEMPT 次，当前 ${CUR}/${SZ}"
  if rsync -a --append-verify --inplace --timeout=120 "$F" "$DST_DIR/$B" >> "$LOG" 2>&1; then
    log "COPY 第 $ATTEMPT 次返回成功"
  else
    log "COPY 第 $ATTEMPT 次失败，5s 后重试"
    sleep 5
  fi
done
CUR="$(stat -c %s "$DST_DIR/$B" 2>/dev/null || echo 0)"
if [ "$CUR" != "$SZ" ]; then
  log "FAIL 大小不符 目标=${CUR} 源=${SZ}"
  echo "RESULT=SIZE_MISMATCH" > "$RES"
  exit 2
fi
log "VERIFY 计算源哈希"
A="$(sha256sum "$F" | cut -d" " -f1)"
if [ -f "$F.sha256" ]; then
  A_F="$(cut -d" " -f1 "$F.sha256" | head -1)"
  if [ "$A" = "$A_F" ]; then log "SRC_HASH_OK 与 .sha256 一致"; else log "SRC_HASH_MISMATCH 源与记录不符"; fi
fi
log "VERIFY 计算目标哈希（63G，约 10 分钟）"
B_H="$(sha256sum "$DST_DIR/$B" | cut -d" " -f1)"
if [ "$A" = "$B_H" ]; then
  log "SUCCESS 校验一致 $B_H"
  printf "%s  %s\n" "$B_H" "$B" > "$DST_DIR/$B.sha256"
  echo "RESULT=OK" > "$RES"
  exit 0
fi
log "FAIL 哈希不一致 源=$A 目标=$B_H"
echo "RESULT=FAIL" > "$RES"
exit 3
