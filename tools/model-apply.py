#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""model-apply.py v1.0 — 按 state/model/policy.json 一键对齐，再交给 model-audit 判定
用法: model-apply.py [--apply]   默认 dry-run
步骤: ①备份 openclaw.json ②config patch 默认兜底链 ③cron 别名改写 ④报告剩余残留
"""
import json, os, shutil, subprocess, sys, time
W = "/home/j/.openclaw/workspace"
P = json.load(open(os.path.join(W, "state/model/policy.json"), encoding="utf-8"))
CFG = "/home/j/.openclaw/openclaw.json"
DO = "--apply" in sys.argv

def run(cmd, stdin=None):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, input=stdin)

# ① 备份
bak = CFG + ".bak-model-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(CFG, bak)
print("[1] 备份 ->", bak)

# ② 默认兜底链
patch = {"agents": {"defaults": {"model": {"fallbacks": P["fallbacks"]}}}}
js = json.dumps(patch, ensure_ascii=False)
chk = run("openclaw config patch --dry-run --stdin", js)
print("[2] 默认兜底链 dry-run:", "OK" if chk.returncode == 0 else chk.stderr.strip()[:200])
if DO and chk.returncode == 0:
    out = run("openclaw config patch --stdin", js)
    print("    应用:", "OK" if out.returncode == 0 else out.stderr.strip()[:200])

# ③ cron 别名 / 漂移改写
d = json.loads(run("openclaw cron list --json").stdout or "{}")
jobs = d if isinstance(d, list) else d.get("jobs", d)
alias = P.get("alias_canonical") or {}
allow = set((P.get("allowed_overrides") or {}).get("jobs") or [])
changed = []
for j in jobs:
    n, jid = j.get("name"), j.get("id")
    m = (j.get("payload") or {}).get("model")
    if not m or n in allow:
        continue
    tgt = alias.get(m) or (P["primary"] if m != P["primary"] else None)
    if not tgt:
        continue
    changed.append((n, m, tgt))
    if DO:
        r = run("openclaw cron edit %s --model %s" % (jid, tgt))
        print("    cron %-24s %s -> %s %s" % (n, m, tgt, "OK" if r.returncode == 0 else "FAIL"))
for n, a, b in changed:
    print("[3] %s: %s -> %s" % (n, a, b))
if not changed:
    print("[3] cron 无需改动")
print("[4] 请跑 python3 tools/model-audit.py 复核")
