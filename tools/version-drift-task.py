#!/usr/bin/env python3
# version-drift-task.py —— 版本漂移时把任务落进账本（由 version-reconcile.sh 调用）
import os, sqlite3, time
DB = "/home/j/.openclaw/workspace/state/tasks/tasks.db"
title = os.environ.get("DRIFT_TITLE", "").strip()
if not title:
    raise SystemExit("no title")
c = sqlite3.connect(DB)
no = (c.execute("select coalesce(max(no),0) from tasks").fetchone()[0] or 0) + 1
now = time.strftime("%Y-%m-%d %H:%M:%S")
cols = [r[1] for r in c.execute("pragma table_info(tasks)")]
row = {"no": no, "title": title, "status": "pending", "grp": "infra", "prio": "2",
       "kind": "task", "owner": "main", "created": now, "updated": now,
       "verify": "bash ~/.openclaw/workspace/tools/version-reconcile.sh; cat state/work/version-drift.json",
       "note": "version-reconcile.sh 自动登记"}
row = {k: v for k, v in row.items() if k in cols}
keys = ",".join(row.keys())
marks = ",".join("?" * len(row))
c.execute("insert into tasks(%s) values(%s)" % (keys, marks), list(row.values()))
c.commit()
print("+#%s %s" % (no, title))
