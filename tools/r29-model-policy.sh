#!/usr/bin/env bash
# R29：模型策略以 2026-11-21 定版为准——所有管家 primary 必须是 deepseek-flash，链路不得含 minimax/kimi
set -u
python3 - <<'PY'
import json,sys
d=json.load(open("/home/j/.openclaw/openclaw.json"))
ents=d["agents"]["entries"]
bad=[]; badfb=[]
for k,v in ents.items():
    m=v.get("model") or {}
    if m.get("primary")!="deepseek/deepseek-flash": bad.append((k,m.get("primary")))
    for f in m.get("fallbacks") or []:
        if "minimax" in f or "kimi" in f: badfb.append((k,f))
if bad: print("FAIL 非 deepseek-flash 主力:", bad[:5], "共", len(bad))
if badfb: print("FAIL 链路含到期厂商:", badfb[:5], "共", len(badfb))
if not bad and not badfb: print("PASS R29 模型池定版（%d 管家全部 deepseek-flash）" % len(ents))
sys.exit(1 if (bad or badfb) else 0)
PY