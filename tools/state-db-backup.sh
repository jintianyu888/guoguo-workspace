#!/bin/bash
# state-db-backup.sh —— state 库分钟级快照 + 小时级异盘复制（2026-11-26 立）
# 用法：state-db-backup.sh [--push]
set -uo pipefail
export PATH=/usr/bin:/bin:/home/j/.npm-global/bin
W=/home/j/.openclaw/workspace
LOG="$W/state/work/state-backup.log"
LOCAL=/home/j/.openclaw/state/backups
DEST=/mnt/d/oc-state-backups
KEEP_LOCAL=96
KEEP_DEST=168
MODE=local
if [ $# -gt 0 ] && [ "$1" = "--push" ]; then MODE=push; fi

mkdir -p "$LOCAL" "$DEST" 2>/dev/null
say(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

if [ "$MODE" = local ]; then
  STAMP=$(date +%Y%m%d-%H%M)
  python3 - "$LOCAL" "$STAMP" <<'PY'
import sqlite3, sys, os
dest, stamp = sys.argv[1], sys.argv[2]
srcs = [("/home/j/.openclaw/state/openclaw.sqlite", "openclaw"),
        ("/home/j/.openclaw/workspace/state/tasks/tasks.db", "tasks")]
bad = 0
for src, name in srcs:
    if not os.path.exists(src):
        continue
    out = os.path.join(dest, "%s-%s.sqlite" % (name, stamp))
    try:
        c = sqlite3.connect("file:" + src + "?mode=ro", uri=True)
        d = sqlite3.connect(out); c.backup(d); d.close(); c.close()
        q = sqlite3.connect(out).execute("pragma quick_check").fetchone()[0]
        sz = os.path.getsize(out) / 1048576
        if q != "ok" or sz < 0.01:
            print("BAD", name, q, sz); bad += 1
    except Exception as e:
        print("ERR", name, e); bad += 1
sys.exit(1 if bad else 0)
PY
  rc=$?
  if [ "$rc" -ne 0 ]; then
    say "✗ 本地快照失败 rc=$rc"
    timeout 60 bash "$W/tools/notify.sh" --alert "【state 备份失败】15 分钟快照未过校验，见 $LOG" >/dev/null 2>&1 || true
    exit 1
  fi
  date +%s > "$LOCAL/.last-ok"
  for n in openclaw tasks; do
    ls -1t "$LOCAL"/$n-*.sqlite 2>/dev/null | tail -n +$((KEEP_LOCAL+1)) | while read -r f; do rm -f "$f"; done
  done
  say "OK 本地快照 $STAMP 用量 $(du -sh "$LOCAL" 2>/dev/null | cut -f1)"
  exit 0
fi

if ! mountpoint -q /mnt/d; then
  say "✗ /mnt/d 未挂载，跳过异盘复制"
  timeout 60 bash "$W/tools/notify.sh" --alert "【state 备份】/mnt/d 未挂载，异盘副本缺失" >/dev/null 2>&1 || true
  exit 1
fi
LATEST_O=$(ls -1t "$LOCAL"/openclaw-*.sqlite 2>/dev/null | head -1)
LATEST_T=$(ls -1t "$LOCAL"/tasks-*.sqlite 2>/dev/null | head -1)
if [ -z "$LATEST_O" ]; then say "✗ 无本地快照可推"; exit 1; fi
for f in "$LATEST_O" "$LATEST_T"; do
  if [ -z "$f" ]; then continue; fi
  b=$(basename "$f")
  cp -f "$f" "$DEST/$b.tmp" && mv -f "$DEST/$b.tmp" "$DEST/$b"
  S1=$(stat -c %s "$f"); S2=$(stat -c %s "$DEST/$b")
  if [ "$S1" != "$S2" ]; then
    say "✗ 复制大小不一致 $b ($S1 vs $S2)"
    timeout 60 bash "$W/tools/notify.sh" --alert "【state 备份】异盘副本大小不一致 $b" >/dev/null 2>&1 || true
    exit 1
  fi
  Q=$(python3 -c "import sqlite3,sys;print(sqlite3.connect(sys.argv[1]).execute('pragma quick_check').fetchone()[0])" "$DEST/$b" 2>/dev/null)
  if [ "$Q" != "ok" ]; then say "✗ 异盘副本校验失败 $b ($Q)"; exit 1; fi
done
for n in openclaw tasks; do
  ls -1t "$DEST"/$n-*.sqlite 2>/dev/null | tail -n +$((KEEP_DEST+1)) | while read -r f; do rm -f "$f"; done
done
say "OK 异盘副本 $(basename "$LATEST_O") → $DEST（$(du -sh "$DEST" 2>/dev/null | cut -f1)）"
