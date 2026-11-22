#!/usr/bin/env bash
# backup-integrity.sh —— 升级前备份完整性检查（2026-11-22 主公令）
# 判据：01:00 全量在 D 与 X 两处同名同大小、且最新一份不超过 30 小时
# 用法：bash tools/backup-integrity.sh [--quiet] [--deep]
set -uo pipefail
DQ=/mnt/d/openclaw-backups
XQ=/mnt/x/openclaw-backups
LOG=/home/j/.openclaw/workspace/state/work/backup-integrity.log
QUIET=0; DEEP=0
for a in "$@"; do case "$a" in --quiet) QUIET=1;; --deep) DEEP=1;; esac; done

say(){ [ "$QUIET" = "1" ] || echo "$*"; }
fail(){ echo "✗ $*" | tee -a "$LOG" >&2; exit 1; }

[ -d "$DQ" ] || fail "D 盘备份目录不可见：$DQ"
[ -d "$XQ" ] || fail "X 盘备份目录不可见：$XQ"

NEWEST=$(ls -t "$DQ"/*openclaw-backup.tar.gz 2>/dev/null | head -1)
[ -n "$NEWEST" ] || fail "D 盘没有全量归档"
BASE=$(basename "$NEWEST")
DSZ=$(stat -c %s "$NEWEST" 2>/dev/null || echo 0)
[ "$DSZ" -gt 1000000000 ] || fail "D 盘最新归档过小（$DSZ 字节）：$BASE"

AGEH=$(( ( $(date +%s) - $(stat -c %Y "$NEWEST") ) / 3600 ))
[ "$AGEH" -le 30 ] || fail "最新归档已 $AGEH 小时（>30h），视为当天备份没跑完：$BASE"

XSZ=$(stat -c %s "$XQ/$BASE" 2>/dev/null || echo 0)
[ "$XSZ" = "$DSZ" ] || fail "X 盘副本缺失或大小不符（D=$DSZ X=$XSZ）：$BASE"

if [ "$DEEP" = "1" ]; then
  python3 - "$NEWEST" "$XQ/$BASE" <<'PY'
import hashlib,os,sys
def sample(p):
    h=hashlib.sha256(); sz=os.path.getsize(p)
    with open(p,"rb") as f:
        h.update(f.read(64*1024*1024))
        if sz > 128*1024*1024:
            f.seek(sz-64*1024*1024); h.update(f.read(64*1024*1024))
    return h.hexdigest()
a,b=sample(sys.argv[1]),sample(sys.argv[2])
sys.exit(0 if a==b else 1)
PY
  [ $? -eq 0 ] || fail "首尾采样哈希不一致：$BASE"
fi

GB=$(( DSZ/1073741824 ))
echo "$(date -Iseconds) PASS $BASE $DSZ $AGEH h" >> "$LOG"
[ "$QUIET" = "1" ] || echo "✓ 备份完整：$BASE（$AGEH 小时前，$GB GB，D/X 一致）"
exit 0
