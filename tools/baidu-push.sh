#!/bin/bash
# baidu-push.sh —— 备份归档加密后单向推送到百度网盘同步目录（不双向同步）
# 用法：--dry 只演示；--latest N 取最新 N 份（默认2）
set -u
W=/home/j/.openclaw/workspace
SRC=${SRC_DIR:-/mnt/e/openclaw-backups}
DST=${DST_DIR:-/mnt/e/openclaw-cloud-backup/备份归档-加密}
KEY=/home/j/.backup-key
CHUNK=4G
LOG=$W/state/work/baidu-push.log
LED=$W/state/baidu-push-ledger.jsonl
DRY=1; N=2
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) DRY=0;;
    --latest) N="$2"; shift;;
  esac; shift
done
mkdir -p "$DST" "$W/state/work"
log() { echo "[$(date "+%F %T")] $*" >> "$LOG"; }
[ -f "$KEY" ] || { umask 077; openssl rand -base64 32 > "$KEY"; chmod 600 "$KEY"; log "已生成加密口令文件 $KEY（请离线抄一份，丢了无法恢复）"; }

mapfile -t FILES < <(ls -t "$SRC"/*.tar.gz 2>/dev/null | head -n "$N")
[ ${#FILES[@]} -gt 0 ] || { log "无归档可推"; exit 0; }
for f in "${FILES[@]}"; do
  b=$(basename "$f")
  h=$(sha256sum "$f" | cut -d" " -f1)
  sz=$(stat -c %s "$f")
  tgt="$DST/$b.gpg"
  if [ -f "$tgt.joined.sha256" ]; then log "已推送过，跳过 $b"; continue; fi
  if [ "$DRY" = "1" ]; then log "[演练] 将加密分片推送 $b (${sz}B, sha256 ${h:0:16})"; continue; fi
  log "开始加密推送 $b"
  gpg --batch --yes --passphrase-file "$KEY" --cipher-algo AES256 --symmetric -o - "$f" 2>>"$LOG" \
    | split -b "$CHUNK" -d -a 3 - "$tgt.part-" || { log "❌ 加密/分片失败 $b"; continue; }
  parts=$(ls "$tgt".part-* 2>/dev/null | wc -l)
  { echo "archive: $b"; echo "size: $sz"; echo "sha256: $h"; echo "parts: $parts"; echo "chunk: $CHUNK"; echo "created: $(date -Iseconds)"; } > "$DST/$b.manifest.txt"
  cat "$tgt".part-* | sha256sum | cut -d" " -f1 > "$tgt.joined.sha256"
  printf '{"ts":"%s","archive":"%s","size":%s,"sha256":"%s","parts":%s,"dst":"%s"}\n' "$(date -Iseconds)" "$b" "$sz" "$h" "$parts" "$DST" >> "$LED"
  log "✅ 完成 $b：$parts 片，清单已写"
done