#!/usr/bin/env python3
"""把 deadletter-hygiene 导出的 JSONL 回灌进 delivery_queue_entries。
用法: python3 tools/deadletter-restore.py <export.jsonl> [--db PATH] [--dry-run]
默认 DB /home/j/.openclaw/state/openclaw.sqlite；单事务 INSERT OR REPLACE，失败整体回滚。
"""
import argparse, json, sqlite3, sys

ap = argparse.ArgumentParser()
ap.add_argument("export")
ap.add_argument("--db", default="/home/j/.openclaw/state/openclaw.sqlite")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

blob = json.load(open(a.export, encoding="utf-8"))
cols, rows = blob["columns"], blob["rows"]
if not rows:
    print("空导出，无需恢复"); sys.exit(0)
sql = f"insert or replace into delivery_queue_entries ({','.join(cols)}) values ({','.join('?'*len(cols))})"
if a.dry_run:
    print(f"dry-run: 将恢复 {len(rows)} 行（导出于 {blob.get('purged_at')}）")
    sys.exit(0)
c = sqlite3.connect(a.db, timeout=30)
c.execute("pragma busy_timeout=30000")
try:
    with c:
        c.executemany(sql, rows)
    print(f"已恢复 {len(rows)} 行 → {a.db}")
except Exception as e:
    print(f"恢复失败，已回滚: {e}"); sys.exit(1)
