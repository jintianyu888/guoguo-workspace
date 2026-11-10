#!/bin/bash
# nas-migrate-run.sh —— 老群晖归档 → 新群晖归档目录，逐份流式搬运 + 边传边算 SHA256
# 背景：老群晖 rsync --server 模式被 DSM 拒绝（要求 root，返回 Permission denied），
#       普通 SSH 命令可用，故改用 cat 流式 + in-flight sha256，断点按「大小一致」跳过。
set -uo pipefail
SRC_HOST=jintianyu@192.168.1.5
SRC_DIR=/volume1/homes/jintianyu/openclaw-archives
DST=/mnt/nas/archive/jinyu/openclaw-archives
LOG=/home/j/.openclaw/workspace/state/work/nas-migrate.log
LOCK=/home/j/.openclaw/workspace/state/work/nas-migrate.lock
exec 9>"$LOCK"; flock -n 9 || { echo "已有实例在跑" >&2; exit 0; }
mkdir -p "$DST"
log(){ printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
# -n 不能省：循环体里调用 ssh 会吞掉 while 读到一半的文件清单（首跑只搬了 1 个就 END 的根因）
S(){ ssh -q -n -o BatchMode=yes -o ConnectTimeout=15 "$SRC_HOST" "$@"; }

log "=== MIGRATE START $(date '+%F %T') ==="
S "cd $SRC_DIR && ls -1 *.tar.gz *.sha256 2>/dev/null" > /tmp/migrate-files.txt || { log "列表失败"; exit 2; }
TOTAL=$(wc -l < /tmp/migrate-files.txt)
log "待处理文件数 $TOTAL"
OK=0; SKIP=0; FAIL=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  rs=$(S "stat -c%s '$SRC_DIR/$f'" 2>/dev/null | tr -d ' \r')
  case "$rs" in ''|*[!0-9]*) log "FAIL 取源大小失败 $f"; FAIL=$((FAIL+1)); continue;; esac
  if [ -f "$DST/$f" ] && [ "$(stat -c%s "$DST/$f" 2>/dev/null)" = "$rs" ]; then
    log "SKIP $f (已存在且大小一致)"; SKIP=$((SKIP+1)); continue
  fi
  log "COPY $f ($rs bytes)"
  if [ "${f##*.}" = "sha256" ]; then
    if S "cat '$SRC_DIR/$f'" > "$DST/$f.part"; then :; fi
    if [ "$(stat -c%s "$DST/$f.part" 2>/dev/null)" = "$rs" ]; then
      mv -f "$DST/$f.part" "$DST/$f"; log "OK $f (sidecar)"; OK=$((OK+1))
    else log "FAIL $f (sidecar 大小不符)"; rm -f "$DST/$f.part"; FAIL=$((FAIL+1)); fi
    continue
  fi
  SHA=$(S "cat '$SRC_DIR/$f'" | tee "$DST/$f.part" | sha256sum | awk '{print $1}')
  if [ "$(stat -c%s "$DST/$f.part" 2>/dev/null)" = "$rs" ]; then
    mv -f "$DST/$f.part" "$DST/$f"
    printf '%s  %s\n' "$SHA" "$f" > "$DST/$f.sha256.tmp" && mv -f "$DST/$f.sha256.tmp" "$DST/$f.sha256"
    log "OK $f size=$rs sha=$SHA"; OK=$((OK+1))
  else
    log "FAIL $f 大小不符 local=$(stat -c%s "$DST/$f.part" 2>/dev/null) want=$rs"; rm -f "$DST/$f.part"; FAIL=$((FAIL+1))
  fi
done < /tmp/migrate-files.txt
log "=== MIGRATE END ok=$OK skip=$SKIP fail=$FAIL $(date '+%F %T') ==="
df -h /mnt/nas | tail -1 >> "$LOG"
