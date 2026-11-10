#!/bin/bash
# backup-hash-job.sh —— 闲时任务：给最新归档算 SHA256 + 同步清单 + 跑保留策略（2026-10-16 主公令 ①②）
# 2026-10-24 修：原先整段 { } >> LOG 2>&1 无 rc 检查，子步骤失败被静默（10-23 06:35 即如此）
set -u -o pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/backup-hash.log
BH=$W/tools/backup-hash.sh
STATUS=$W/state/backup-hash-last.json
fail=0
step=none
# 2026-10-26 A2 修：加单实例锁（12:10 手工复跑与 12:20 定时撞车，两个 write-latest 同时哈希 84GB）
exec 8>"$W/state/work/backup-hash-job.lock"
flock -n 8 || { echo "$(date '+%F %T') SKIP 已有实例在跑" >> "$LOG"; exit 0; }
{
  echo "=== START $(date '+%F %T') 闲时哈希任务 ==="

  step=write-latest
  sh "$BH" write-latest /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups
  rc=$?
  if [ "$rc" -ne 0 ]; then echo "  [FAIL] $step rc=$rc"; fail=1; else echo "  [OK] $step"; fi
  # 2026-11-07 #164：write-latest 后必须逐目录验证最新归档确有 .sha256 + .sha256.meta，
  # 只靠 rc 会把「缓存命中/无清单」当成功（假绿）
  for d in /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
    [ -d "$d" ] || continue
    nf=$(ls -t "$d"/*.tar.gz 2>/dev/null | head -1)
    [ -n "$nf" ] || { echo "  [FAIL] $d 下没有归档"; fail=1; continue; }
    _h=$( [ -f "$nf.sha256" ] && head -1 "$nf.sha256" | awk '{print $1}' )
    if [ -f "$nf.sha256" ] && [ -f "$nf.sha256.meta" ] && printf '%s' "$_h" | grep -Eq '^[0-9a-f]{64}$'; then
      echo "  [OK] 哈希齐备: $(basename "$nf")"
    else
      echo "  [FAIL] 缺哈希或meta: $(basename "$nf")"; fail=1
    fi
  done


  step=sync-manifest
  for F in /mnt/d/openclaw-backups/*.sha256; do
    [ -f "$F" ] || continue
    B=$(basename "$F")
    for X in /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
      if [ -f "$X/${B%.sha256}" ] && [ ! -f "$X/$B" ]; then
        if cp -f "$F" "$X/"; then echo "  清单同步→$X: $B"; else echo "  [FAIL] 同步→$X: $B"; fail=1; fi
      fi
    done
  done

  step=retain
  bash "$W/tools/backup-retain.sh"
  rc=$?
  if [ "$rc" -ne 0 ]; then echo "  [FAIL] $step rc=$rc"; fail=1; else echo "  [OK] $step"; fi

  echo "=== DONE $(date '+%F %T') fail=$fail ==="
} >> "$LOG" 2>&1

printf '{"ts":"%s","fail":%d,"step":"%s"}\n' "$(date '+%F %T')" "$fail" "$step" > "$STATUS" 2>/dev/null || true

if [ "$fail" -ne 0 ]; then
  bash "$W/tools/notify.sh" "🔴 备份哈希任务失败 step=$step 详见 $LOG" >/dev/null 2>&1 || true
  exit 1
fi
exit 0
