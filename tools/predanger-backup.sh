#!/bin/bash
# predanger-backup.sh —— 危险操作前的即时全量备份（主公 2026-10-23 令，双审通过）
# 落点：/mnt/e/openclaw-predanger（2026-11-02 主公令：D 盘不再放备份）；镜像目录 /mnt/h/openclaw-predanger —— backup-retain.sh 只扫 */openclaw-backups，
#       故此目录天然免疫日常保留清理，也不占用 D=2 名额。
# 保留：最多 8 份；超限且已满 7 天 → 三重校验(同名+同大小+SHA256)过了才移回收，否则保留并记日志。
# 用法: predanger-backup.sh "原因" [--dry-run] [--mirror-e]
set -uo pipefail
W=/home/j/.openclaw/workspace
WHY="${1:-未说明}"; shift || true
DRY=0; MIRROR_E=0
for a in "$@"; do case "$a" in --dry-run) DRY=1;; --mirror-e) MIRROR_E=1;; esac; done
DIR_P=/mnt/e/openclaw-predanger
DIR_M=/mnt/h/openclaw-predanger
LOG=$W/state/work/predanger.log
LEDGER=$W/state/predanger-ledger.jsonl
KEEP_MAX=8
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

mkdir -p "$DIR_P" "$DIR_M" "$(dirname "$LEDGER")" "$(dirname "$LOG")"
say "=== PREDANGER START 原因=$WHY dry=$DRY ==="

if [ "$DRY" = "1" ]; then
  say "演练模式：不生成新备份，只演练保留清理"
else
  sh "$W/tools/gen-recovery-doc.sh" >>"$LOG" 2>&1
  openclaw backup create --output "$DIR_P" --verify >>"$LOG" 2>&1
  RC=$?
  NEW=$(ls -t "$DIR_P"/*.tar.gz 2>/dev/null | head -1)
  if [ "$RC" != "0" ] || [ -z "$NEW" ]; then
    say "❌ 危险操作前备份失败 rc=$RC —— 禁止继续，先排查"
    exit 1
  fi
  SZ=$(stat -c %s "$NEW"); SH=$(sha256sum "$NEW" | cut -d' ' -f1)
  say "✅ 已生成 $(basename "$NEW") ($(du -h "$NEW" | cut -f1)) sha256=${SH:0:16}…"
  printf '{"ts":"%s","reason":"%s","file":"%s","bytes":%s,"sha256":"%s"}\n' \
    "$(date -Is)" "$WHY" "$(basename "$NEW")" "$SZ" "$SH" >> "$LEDGER"
  if [ "$MIRROR_E" = "1" ]; then
    say "镜像到 E（23.8G 约 20-40 分钟，后台跑）"
    nohup cp -f "$NEW" "$DIR_M/" >>"$LOG" 2>&1 &
  fi
fi

COUNT=$(ls -1 "$DIR_P"/*.tar.gz 2>/dev/null | wc -l)
say "当前 predanger 档数：$COUNT（上限 $KEEP_MAX）"
if [ "$COUNT" -gt "$KEEP_MAX" ]; then
  ls -t "$DIR_P"/*.tar.gz 2>/dev/null | tail -n +$((KEEP_MAX+1)) | while IFS= read -r f; do
    [ -f "$f" ] || continue
    nm=$(basename "$f"); age=$(( ( $(date +%s) - $(stat -c %Y "$f" 2>/dev/null || echo 0) ) / 86400 ))
    if [ "$age" -lt 7 ]; then say "  保留(未满7天 age=${age}d)：$nm"; continue; fi
    sz=$(stat -c %s "$f"); sh=$(sha256sum "$f" | cut -d' ' -f1)
    ok=0
    for d in "$DIR_M" /mnt/h/openclaw-predanger /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
      c="$d/$nm"
      [ -f "$c" ] || continue
      [ "$(stat -c %s "$c" 2>/dev/null)" = "$sz" ] || continue
      [ "$(sha256sum "$c" | cut -d' ' -f1)" = "$sh" ] || continue
      ok=1; break
    done
    if [ "$ok" != "1" ]; then say "  ⏭ 保留(别处无三重校验副本)：$nm"; continue; fi
    if [ "$DRY" = "1" ]; then say "  [演练] 将移回收：$nm"; else
      dest=/mnt/e/openclaw-trash/predanger-$(date +%Y%m%d-%H%M)
      mkdir -p "$dest" && mv -f "$f" "$dest/" && say "  🧹 已移回收：$nm → $dest"
    fi
  done
fi
say "=== PREDANGER END ==="

