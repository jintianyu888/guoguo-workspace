#!/bin/bash
# code-repo-backup.sh —— 代码仓本地备份链（2026-11-10 立，零 token）
# 打包 /home/j/openclaw-git/guoguo 为 git bundle → gpg AES256 → 落本机 + E 盘 + 群晖，保留最近 N 份。
# 用法：bash tools/code-repo-backup.sh [--dry-run]
set -u
W=/home/j/.openclaw/workspace
REPO=/home/j/openclaw-git/guoguo
KEY=/home/j/.openclaw/secrets-in/t1.key
LOCAL=$W/state/backup/code
E=/mnt/e/openclaw-backups/code
NAS=/mnt/nas/archive/jinyu/openclaw-archives/code
LOG=$W/state/work/code-backup.log
KEEP_LOCAL=8; KEEP_E=8; KEEP_NAS=6
TS=$(date +%Y%m%d-%H%M%S)
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
log(){ echo "[$(date '+%F %T')] $*" >>"$LOG"; }

[ -d "$REPO/.git" ] || { log "ERR 无仓库 $REPO"; echo "仓库不存在"; exit 1; }
mkdir -p "$LOCAL" "$(dirname "$LOG")" 2>/dev/null
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

SHA=$(git -C "$REPO" rev-parse --short HEAD)
CNT=$(git -C "$REPO" ls-files | wc -l)
if [ "$DRY" = "1" ]; then
  echo "dry-run：仓库 $REPO @ $SHA · 文件 $CNT · 将打包并加密到 $LOCAL"
  exit 0
fi

git -C "$REPO" bundle create "$TMP/guoguo-$TS.bundle" --all >/dev/null 2>&1 || { log "ERR bundle 失败"; echo "打包失败"; exit 1; }
printf 'repo=%s\ncommit=%s\nfiles=%s\nts=%s\n' "$REPO" "$SHA" "$CNT" "$TS" > "$TMP/MANIFEST.txt"
tar czf "$TMP/code-$TS.tar.gz" -C "$TMP" "guoguo-$TS.bundle" MANIFEST.txt
ENC="$LOCAL/guoguo-code-$TS.tar.gz.gpg"
if [ -f "$KEY" ]; then
  gpg --batch --yes --quiet --passphrase-file "$KEY" --symmetric --cipher-algo AES256 -o "$ENC" "$TMP/code-$TS.tar.gz" 2>>"$LOG" || { log "ERR gpg 失败"; echo "加密失败"; exit 1; }
  rm -f "$TMP/code-$TS.tar.gz"
else
  log "WARN 无密钥 $KEY，落明文包"
  cp -f "$TMP/code-$TS.tar.gz" "$LOCAL/"
  ENC="$LOCAL/code-$TS.tar.gz"
fi
# 自校验：能解密并解出 bundle，否则判失败（零成本的还原证明）
VT="$TMP/verify"; mkdir -p "$VT"
if gpg --batch --yes --quiet --passphrase-file "$KEY" --decrypt -o "$VT/v.tar.gz" "$ENC" 2>/dev/null    && tar tzf "$VT/v.tar.gz" | grep -q 'MANIFEST.txt'; then
  log "verify OK"
else
  log "ERR verify 失败：$ENC 无法解密/解包"
  mv -f "$ENC" "$ENC.FAILED"
  echo "❌ 自校验失败，已标记 .FAILED：$ENC"
  exit 1
fi

SZ=$(stat -c %s "$ENC")
sha256sum "$ENC" | awk '{print $1}' > "$ENC.sha256"

# 分发
for D in "$E" "$NAS"; do
  case "$D" in
    "$E") mountpoint -q /mnt/e || { log "skip E 未挂载"; continue; } ;;
    "$NAS") mountpoint -q /mnt/nas || { log "skip NAS 未挂载"; continue; } ;;
  esac
  mkdir -p "$D" 2>/dev/null
  cp -f "$ENC" "$ENC.sha256" "$D"/ 2>/dev/null && log "copy -> $D" || log "WARN copy 失败 $D"
done

# 轮转（按份数，删除前记 sha256 头）
rot(){ local dir="$1" keep="$2"; [ -d "$dir" ] || return 0
  local n; n=$(ls -1 "$dir"/guoguo-code-*.gpg "$dir"/code-*.tar.gz 2>/dev/null | wc -l)
  [ "$n" -le "$keep" ] && return 0
  ls -1t "$dir"/guoguo-code-*.gpg "$dir"/code-*.tar.gz 2>/dev/null | tail -n $((n-keep)) | while read -r f; do
    log "rotate-del $(basename "$f") sha=$(sha256sum "$f" 2>/dev/null | cut -c1-16)"
    rm -f "$f" "$f.sha256"
  done
}
rot "$LOCAL" "$KEEP_LOCAL"; rot "$E" "$KEEP_E"; rot "$NAS" "$KEEP_NAS"

echo "✅ 代码仓备份 $SHA · $(numfmt --to=iec $SZ) · $ENC"
log "OK $SHA size=$SZ files=$CNT"
