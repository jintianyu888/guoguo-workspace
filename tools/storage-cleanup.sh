#!/bin/bash
# storage-cleanup.sh v2 —— 分批复核式清理（最稳妥版）
# 默认演练；--apply 才执行。校验不过一律不删。
set -uo pipefail
W=/home/j/.openclaw/workspace
LED=$W/state/storage-cleanup-ledger.jsonl
LOG=$W/state/work/storage-cleanup.log
TRASH=/mnt/e/openclaw-trash/$(date +%Y%m%d-%H%M)
APPLY=0; BATCH=b1
for a in "$@"; do case "$a" in --apply) APPLY=1;; b1|b2|b3) BATCH=$a;; esac; done
log(){ echo "[$(date "+%F %T")] $*" | tee -a "$LOG"; }
ledger(){ printf '{"ts":"%s","batch":"%s","item":"%s","bytes":%s,"replica":"%s","action":"%s"}\n' "$(date -Is)" "$BATCH" "$1" "${2:-0}" "$3" "$4" >> "$LED"; }
# 校验：源 与 副本 同名(文件) + 同大小 + (目录再比文件数)
okdup(){
  local s=$1 d=$2 ss ds
  [ -e "$s" ] && [ -e "$d" ] || return 1
  if [ -d "$s" ]; then
    ss=$(timeout 600 du -sb "$s" 2>/dev/null | cut -f1)
    ds=$(timeout 600 du -sb "$d" 2>/dev/null | cut -f1)
    [ -n "$ss" ] && [ "$ss" = "$ds" ] || return 1
    local a b; a=$(timeout 300 find "$s" -type f 2>/dev/null | wc -l); b=$(timeout 300 find "$d" -type f 2>/dev/null | wc -l)
    [ "$a" = "$b" ] || return 1
  else
    ss=$(stat -c %s "$s" 2>/dev/null); ds=$(stat -c %s "$d" 2>/dev/null)
    [ -n "$ss" ] && [ "$ss" = "$ds" ] || return 1
  fi
  echo "$ss"
}
kill_item(){ # path replica label
  local p=$1 rep=$2 lab=$3 sz
  sz=$(okdup "$p" "$rep") || { log "SKIP 校验不过: $lab"; return 1; }
  log "校验通过: $lab (${sz}B) 副本=$rep"
  if [ "$APPLY" = "1" ]; then
    if [ -d "$p" ]; then mkdir -p "$TRASH"; mv -f "$p" "$TRASH/" && ledger "$lab" "$sz" "$rep" "trash-moved"; 
    else mkdir -p "$TRASH"; mv -f "$p" "$TRASH/" && ledger "$lab" "$sz" "$rep" "trash-moved"; fi
    log "已移入回收站: $lab";
  else log "[演练] 将移入回收站: $lab"; fi
}
log "=== START batch=$BATCH apply=$APPLY ==="
case "$BATCH" in
b1)
  hs=$(grep -cE "^[0-9a-f]{64}" "$W/state/work/b1-sha256.txt" 2>/dev/null || echo 0)
  uq=$(grep -hoE "^[0-9a-f]{64}" "$W/state/work/b1-sha256.txt" 2>/dev/null | sort -u | wc -l)
  if [ "${hs:-0}" -lt 2 ] || [ "${uq:-0}" -ne 1 ]; then
    log "SKIP X整机tar：缺少两份一致的 sha256 指纹（已算 $hs 份，唯一值 $uq）"
  else
    kill_item /mnt/x/wsl-backup/ubuntu-20261022.tar /mnt/e/wsl-backup/ubuntu-20261022.tar "X整机tar"
  fi
  kill_item /home/j/.openclaw-trash/20261019-fast-experiment /mnt/e/openclaw-store/20261019-fast-experiment "WSL试验批次"
  ;;
b2)
  while IFS= read -r f; do
    b=$(basename "$f"); s=$(stat -c %s "$f" 2>/dev/null)
    rep=$(ls -1 /mnt/h/openclaw-backups/"$b" /mnt/d/openclaw-backups/"$b" 2>/dev/null | head -1)
    [ -n "$rep" ] || { log "SKIP 无副本: $b"; continue; }
    kill_item "$f" "$rep" "E_trash/$b"
  done < <(find /mnt/e/openclaw-backups/_trash -type f -name "*.tar.gz" 2>/dev/null)
  ;;
b3)
  mapfile -t d < <(ls -1t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | tail -n +3)
  for f in "${d[@]:-}"; do
    [ -n "$f" ] || continue; b=$(basename "$f")
    rep=$(ls -1 /mnt/e/openclaw-backups/"$b" /mnt/h/openclaw-backups/"$b" 2>/dev/null | head -1)
    [ -n "$rep" ] || { log "SKIP 无副本: $b"; continue; }
    kill_item "$f" "$rep" "D_old/$b"
  done
  ;;
esac
log "=== END ==="

