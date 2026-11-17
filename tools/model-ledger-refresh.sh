#!/bin/bash
# model-ledger-refresh.sh v1.0 (2026-11-17) —— 模型账本日常刷新（零 token）
set -u
W=/home/j/.openclaw/workspace
cd "$W" || exit 1
LOG=$W/state/model-econ/refresh.log
{
  echo "=== $(date '+%F %T') ==="
  python3 tools/model-ledger.py sync-config
  python3 tools/model-ledger.py quota
  python3 tools/model-ledger.py promo-import
  python3 tools/model-ledger.py doctor
  python3 tools/model-ledger.py report --md
} >>"$LOG" 2>&1
# 只在有到期项/风险时推送
python3 - <<'PY' >>"$LOG" 2>&1
import json, subprocess, os, datetime
db = "/home/j/.openclaw/workspace/state/model-econ/ledger.db"
import sqlite3
c = sqlite3.connect(db)
today = datetime.date.today()
alerts = []
for pid, desc, exp, act in c.execute("SELECT id,desc,expires_at,action FROM promos WHERE status='active'"):
    if exp and len(exp) >= 10:
        try:
            d = datetime.date.fromisoformat(exp[:10]); left = (d - today).days
            if left <= 7: alerts.append(f"· {desc}：{'已过期' if left < 0 else f'剩 {left} 天'} → {act}")
        except Exception: pass
rows = c.execute("SELECT primary_model, COUNT(*) n FROM assignments GROUP BY primary_model ORDER BY n DESC").fetchall()
tot = sum(r[1] for r in rows) or 1
if rows and rows[0][1] / tot > 0.75:
    alerts.append(f"· 分配集中度：{rows[0][0]} 占 {round(100*rows[0][1]/tot)}%（{rows[0][1]}/{tot}）")
if alerts:
    subprocess.run(["bash", "/home/j/.openclaw/workspace/tools/notify.sh",
                    "【模型账本】需处理\n" + "\n".join(alerts)], timeout=30)
print("alerts:", len(alerts))
PY

