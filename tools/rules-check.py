#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rules-check.py — 规矩可执行化（零 token）
读 tools/rules.json，逐条跑检查命令；rc=0 为合规。
输出: 屏幕 + state/work/rules-latest.json
"""
import json, os, subprocess, sys, datetime
W = "/home/j/.openclaw/workspace"
R = json.load(open(os.path.join(W, "tools/rules.json")))
rows = []
for r in R["rules"]:
    try:
        p = subprocess.run(["bash", "-lc", r["check"]], cwd=W, capture_output=True, text=True, timeout=90)
        ok = (p.returncode == 0)
        err = (p.stderr or p.stdout or "").strip().splitlines()[-1:] 
        err = err[0][:70] if err else ""
    except Exception as e:
        ok, err = False, str(e)[:70]
    rows.append({"id": r["id"], "title": r["title"], "ok": ok, "fix": r.get("fix", ""), "err": err})
bad = [x for x in rows if not x["ok"]]
print("== 规矩稽核 %d 条：合规 %d，违反 %d" % (len(rows), len(rows) - len(bad), len(bad)))
for x in rows:
    print("  %s %s %s%s" % ("✅" if x["ok"] else "❌", x["id"], x["title"], "" if x["ok"] else "  → " + x["fix"]))
os.makedirs(os.path.join(W, "state/work"), exist_ok=True)
if bad:
    with open(os.path.join(W, "state/work/rule-violations.jsonl"), "a") as f:
        ts = datetime.datetime.now().strftime("%F %T")
        for x in bad:
            f.write(json.dumps({"at": ts, "id": x["id"], "title": x["title"]}, ensure_ascii=False) + "\n")
json.dump({"at": datetime.datetime.now().strftime("%F %T"), "rows": rows},
          open(os.path.join(W, "state/work/rules-latest.json"), "w"), ensure_ascii=False, indent=1)
sys.exit(1 if bad else 0)
