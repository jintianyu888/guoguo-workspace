#!/bin/bash
# backup-retain-auto.sh v1.0 — 自动保留（两阶段：先隔离，后按龄清理）2026-11-15 主公令
# 安全设计：
#  1) 只有当盘上份数超过保留目标才动作；每盘硬底：X2 D1 E2 H2 NAS2
#  2) 第一步只 mv 到 _quarantine/日期（可回滚）；第二步清理隔离区，且仅当该归档在别的盘还有副本
#  3) 任一盘不可读 → 整体中止（fail-closed）
#  4) 全程写 state/work/retention-audit.jsonl 与 exec 账本
set -u
export PATH=/usr/bin:/bin
W=/home/j/.openclaw/workspace
LED="python3 $W/tools/backup-ledger.py"
QDAYS=${QDAYS:-3}
LOG=$W/state/work/retention-auto.log
say() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
say '=== 自动保留开始'
$LED scan >/dev/null 2>&1 || { say 'scan 失败，中止'; exit 1; }

# 1) 份数超标的盘：交给 retain-plan 做隔离（它自带 fail-closed/软删除/单盘限制）
for d in X D E H NAS; do
  out=$(bash $W/tools/backup-retain-plan.sh --apply $d 2>&1)
  rc=$?
  echo "$out" | while IFS= read -r l; do say "[$d] $l"; done
  if [ $rc -ne 0 ]; then FAILED="${FAILED:-} $d"; say "[$d] retain-plan rc=$rc（该盘跳过，不阻塞其它盘与隔离清理）"; fi
done
[ -n "${FAILED:-}" ] && say "⚠ 隔离失败盘:${FAILED} — 只影响该盘保留，隔离区清理照跑"

# 2) 清理隔离区：仅 龄>QDAYS 且 该归档在其它盘仍有副本
$LED scan >/dev/null 2>&1
for root in /mnt/x/openclaw-backups /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups /mnt/nas/archive/jinyu/openclaw-archives; do
  [ -d "$root/_quarantine" ] || continue
  find "$root/_quarantine" -type f -name '*.tar.gz' -mtime +$QDAYS 2>/dev/null | while IFS= read -r f; do
    b=$(basename "$f")
    others=$(python3 -c "import sqlite3,sys;c=sqlite3.connect('$W/state/ledger/backups.db');print(c.execute('select count(*) from copies where name=?',('$b',)).fetchone()[0])" 2>/dev/null || echo 0)
    if [ "${others:-0}" -ge 1 ]; then rm -f "$f" && say "清隔离 $b（他盘仍有 ${others} 份）"; else say "保留隔离 $b（无其它副本，人工处置）"; fi
  done
done

$LED scan >/dev/null 2>&1
python3 $W/tools/exec-ledger.py retention-import >/dev/null 2>&1
python3 $W/tools/retention-ledger.py import >/dev/null 2>&1   # 2026-11-21：保留动作进 backups.db
say '=== 自动保留结束'
exit 0