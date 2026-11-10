#!/usr/bin/env bash
# lcm-maintenance.sh — 每日低峰维护：WAL 截断 + 条件 VACUUM（不锁长时间）
# 用法: bash tools/lcm-maintenance.sh [--force-vacuum]
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/lcm-maintenance.log
TS=$(date '+%F %T')
mkdir -p "$W/state"

# 避开备份/断网窗口与 IO 卡死
if pgrep -f 'pre-upgrade-backup|backup-tier|backup-daily' >/dev/null 2>&1; then
  echo "[$TS] 备份进行中，跳过" >> "$LOG"; exit 0
fi

exec 3>&1
python3 - "$@" <<'PY' 2>&1 | tee -a "$LOG"
import os, sqlite3, sys, time
paths = [os.path.expanduser("~/.openclaw/lcm.db"),
         os.path.expanduser("~/.openclaw/state/openclaw.sqlite")]
force = "--force-vacuum" in sys.argv
ts = time.strftime("%F %T")
for p in paths:
    if not os.path.exists(p):
        print(f"[{ts}] 跳过（不存在）{p}"); continue
    before = os.path.getsize(p)
    print(f"[{ts}] {p} 开始 大小={before/1e6:.1f}MB")
    try:
        con = sqlite3.connect(p, timeout=10)
        con.execute("PRAGMA busy_timeout=8000")
        (busy, log_frames, ckpt_frames) = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        print(f"[{ts}]   checkpoint: busy={busy} log={log_frames} ckpt={ckpt_frames}")
        after = os.path.getsize(p)
        # 只在 checkpoint 干净且文件较大时尝试 VACUUM（独占锁，失败即放弃）
        in_window = time.strftime('%H') in ('02','03','04')
        if busy == 0 and (force or (before > 100*1024*1024 and in_window)):
            try:
                t0 = time.time()
                con.execute("VACUUM")
                print(f"[{ts}]   VACUUM 完成 {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"[{ts}]   VACUUM 跳过/失败（预期内，库被占用）: {e}")
        con.close()
        after = os.path.getsize(p)
        print(f"[{ts}]   结束 大小={after/1e6:.1f}MB 释放={(before-after)/1e6:.1f}MB")
    except Exception as e:
        print(f"[{ts}]   错误: {e}")
PY
