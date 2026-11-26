#!/bin/bash
# l1-db-sync.sh —— 近实时数据库异机快照（2026-11-26 重立；旧 git 版自 11-07 停摆）
set -uo pipefail
export PATH=/usr/bin:/bin:/home/j/.npm-global/bin
W=/home/j/.openclaw/workspace
LOG="$W/state/work/l1-db-sync.log"
DEST=/mnt/nas/archive/jinyu/db-snapshots
KEEP_DAYS=7
DAY=$(date +%Y%m%d)
HH=$(date +%H%M)
say(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

if ! mountpoint -q /mnt/nas; then
  say "✗ /mnt/nas 未挂载，跳过"
  timeout 60 bash "$W/tools/notify.sh" --alert "【L1 数据库快照】群晖未挂载，异机副本缺失" >/dev/null 2>&1 || true
  exit 1
fi
TMPD=$(mktemp -d /tmp/l1db-XXXX)
cleanup(){ if [ -n "$TMPD" ]; then rm -rf "$TMPD"; fi; }
trap cleanup EXIT

python3 - "$TMPD" <<'PY'
import sqlite3, sys, os
out = sys.argv[1]
srcs = [("/home/j/.openclaw/state/openclaw.sqlite", "openclaw"),
        ("/home/j/.openclaw/workspace/state/tasks/tasks.db", "tasks")]
for src, name in srcs:
    if not os.path.exists(src):
        continue
    dst = os.path.join(out, name + ".sqlite")
    c = sqlite3.connect("file:" + src + "?mode=ro", uri=True)
    c.execute("VACUUM INTO '" + dst.replace("'", "''") + "'")
    c.close()
    q = sqlite3.connect(dst).execute("pragma integrity_check").fetchone()[0]
    if q != "ok":
        print("BAD", name, q); sys.exit(1)
    print("ok", name, "%.1fMB" % (os.path.getsize(dst)/1048576))
PY
[ $? -eq 0 ] || { say "✗ 快照生成/校验失败"; timeout 60 bash "$W/tools/notify.sh" --alert "【L1 数据库快照】生成失败，见 $LOG" >/dev/null 2>&1 || true; exit 1; }

mkdir -p "$DEST/$DAY" || { say "✗ 建目标目录失败"; exit 1; }
for f in "$TMPD"/*.sqlite; do
  b=$(basename "$f" .sqlite)
  cp -f "$f" "$DEST/$DAY/$b-$HH.sqlite.part" && mv -f "$DEST/$DAY/$b-$HH.sqlite.part" "$DEST/$DAY/$b-$HH.sqlite"
  S1=$(stat -c %s "$f"); S2=$(stat -c %s "$DEST/$DAY/$b-$HH.sqlite" 2>/dev/null || echo 0)
  if [ "$S1" != "$S2" ]; then
    say "✗ $b 复制大小不一致 ($S1 vs $S2)"
    rm -f "$DEST/$DAY/$b-$HH.sqlite"
    timeout 60 bash "$W/tools/notify.sh" --alert "【L1 数据库快照】$b 复制校验失败" >/dev/null 2>&1 || true
    exit 1
  fi
done

find "$DEST" -maxdepth 1 -type d -name "20*" -mtime +$KEEP_DAYS -exec rm -rf {} + 2>/dev/null
say "OK $DAY/$HH → $DEST（$(du -sh "$DEST" 2>/dev/null | cut -f1)）"
tail -n 400 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
