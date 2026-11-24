#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-registry.py v1.0 — 验收覆盖率总账（零 token）
主公 2026-11-24 令：所有任务和问题都要有验收机制。
规则：
  in_progress 必须有机器可跑命令（verify 不以 HUMAN: 开头）
  pending/paused 允许 HUMAN:<等待条件>，但每周复审
  任何 open 任务都没口径 = 红
用法: verify-registry.py [--json] [--check]
"""
import json, os, shutil, sqlite3, subprocess, sys, datetime
W = "/home/j/.openclaw/workspace"
DB = os.path.join(W, "state/tasks/tasks.db")
tmp = "/tmp/vr-tasks.db"
shutil.copy2(DB, tmp)
c = sqlite3.connect(tmp)
rows = c.execute("select no,title,status,verify,wait_user from tasks where status in ('pending','in_progress','paused') order by no").fetchall()
open_rows, missing, human_only = [], [], []
for no, title, st, v, wu in rows:
    v = (v or "").strip()
    rec = {"no": no, "title": (title or "")[:50], "status": st}
    if not v:
        missing.append(rec)
    elif v.upper().startswith("HUMAN:"):
        if st == "in_progress":
            human_only.append(rec)
    open_rows.append(rec)
cov = len(open_rows) - len(missing)
res = {"date": datetime.date.today().isoformat(), "open_tasks": len(open_rows),
       "with_verify": cov, "missing": missing,
       "in_progress_human_only": human_only,
       "coverage_pct": round(cov * 100.0 / max(len(open_rows), 1), 1)}
if "--check" in sys.argv:
    q = subprocess.run([sys.executable, os.path.join(W, "tools/verify-queue.py"), "check"], capture_output=True, text=True)
    res["queue_rc"] = q.returncode
    res["queue_tail"] = (q.stdout or q.stderr).strip().splitlines()[-3:]
os.makedirs(os.path.join(W, "state/verify"), exist_ok=True)
p = os.path.join(W, "state/verify/coverage-%s.json" % res["date"])
json.dump(res, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if "--json" in sys.argv:
    print(json.dumps(res, ensure_ascii=False, indent=1))
else:
    print("验收覆盖率：%d/%d = %s%%  （%s）" % (cov, len(open_rows), res["coverage_pct"], res["date"]))
    for m in missing:
        print("  ✗ 无口径 #%s %s" % (m["no"], m["title"]))
    for m in human_only:
        print("  ⚠ in_progress 只有人工口径 #%s %s" % (m["no"], m["title"]))
    print("GREEN 全部有验收口径" if not missing and not human_only else "RED 有缺口")
sys.exit(0 if (not missing and not human_only) else 1)
