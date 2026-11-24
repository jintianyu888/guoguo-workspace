#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""model-audit.py v1.0 — 模型切换残留审计（零 token）
读 state/model/policy.json（唯一真源）与 openclaw.json / cron / advisors，
任何不一致即报 drift，rc=1。用法: model-audit.py [--json]
"""
import json, subprocess, sys, os
W = "/home/j/.openclaw/workspace"
P = json.load(open(os.path.join(W, "state/model/policy.json"), encoding="utf-8"))
CFG = json.load(open("/home/j/.openclaw/openclaw.json", encoding="utf-8"))
drift = []

def add(kind, where, got, want):
    drift.append({"kind": kind, "where": where, "got": got, "want": want})

ag = CFG.get("agents", {})
ent = ag.get("entries") or {}
dflt = ag.get("defaults", {}).get("model") or {}

# 1 管家主模型 + 兜底链
for k, v in ent.items():
    m = v.get("model")
    if m is None:
        continue
    p = m.get("primary") if isinstance(m, dict) else m
    if p != P["primary"]:
        add("agent.primary", k, p, P["primary"])
    if isinstance(m, dict) and m.get("fallbacks") is not None:
        fb = list(m["fallbacks"])
        if fb != P["fallbacks"]:
            add("agent.fallbacks", k, fb, P["fallbacks"])

# 2 默认兜底链（全局继承源）
dfb = list(dflt.get("fallbacks") or [])
if dfb != P["fallbacks"]:
    add("defaults.fallbacks", "agents.defaults", dfb, P["fallbacks"])

# 3 禁用厂商不得出现在任何链里
chains = [dfb] + [ (v.get("model") or {}).get("fallbacks") or [] for v in ent.values() if isinstance(v.get("model"), dict) ]
for c in chains:
    for b in P["banned_in_chains"]:
        if any(b in str(x) for x in c):
            add("banned.in_chain", "fallbacks", b, "removed")

# 4 cron 载荷模型（白名单外必须是 primary；别名必须规范化）
try:
    out = subprocess.run(["openclaw", "cron", "list", "--json"], capture_output=True, text=True, timeout=90).stdout
    d = json.loads(out); jobs = d if isinstance(d, list) else d.get("jobs", d)
except Exception as e:
    jobs = []
    add("cron.read", "cron list", str(e)[:80], "readable")
allow = set((P.get("allowed_overrides") or {}).get("jobs") or [])
alias = P.get("alias_canonical") or {}
for j in jobs:
    n = j.get("name")
    m = (j.get("payload") or {}).get("model")
    if not m:
        continue
    if m in alias:
        add("cron.alias", n, m, alias[m]); continue
    if n in allow:
        continue
    if m != P["primary"]:
        add("cron.model", n, m, P["primary"])

# 5 顾问槽
try:
    adv = json.load(open(os.path.join(W, "state/advice/advisors.json"), encoding="utf-8"))["advisors"]
    for k, want in (P.get("advisor") or {}).items():
        got = (adv.get(k) or {}).get("model")
        if got and got != want:
            add("advisor", k, got, want)
except Exception as e:
    add("advisor.read", "advisors.json", str(e)[:60], "readable")

res = {"policy_version": P.get("version"), "primary": P["primary"], "drift_count": len(drift), "drift": drift}
if "--json" in sys.argv:
    print(json.dumps(res, ensure_ascii=False, indent=1))
else:
    print("模型池审计：policy v%s 主=%s 残留=%d" % (P.get("version"), P["primary"], len(drift)))
    for x in drift[:30]:
        print("  ✗ %-16s %-28s got=%s want=%s" % (x["kind"], x["where"], x["got"], x["want"]))
    print("GREEN 零残留" if not drift else "RED 有残留，用 tools/model-apply.py --apply 修")
sys.exit(0 if not drift else 1)
