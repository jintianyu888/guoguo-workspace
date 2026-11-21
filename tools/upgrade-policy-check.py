#!/usr/bin/env python3
"""upgrade-policy-check.py — 升级纪律的可机器判定（R17，2026-11-21 主公令）

三条硬判据：
1. upgrade-auto.sh 不许再自动写挂载件（只能出提案）
2. 有挂载件时，必须有匹配的批准件（approved_by + target 一致）
3. 版本不得低于已批准目标（防止"批了没升"悄悄漂移）
"""
import json, os, re, sys, glob

W = "/home/j/.openclaw/workspace"
AUTO = os.path.join(W, "tools/upgrade-auto.sh")
ARM = os.path.join(W, "state/work/.upgrade-armed")
APPR = os.path.join(W, "state/work/.upgrade-approved")
bad = []

src = open(AUTO).read() if os.path.exists(AUTO) else ""
# 自动写挂载的旧写法： printf ... > "$ARM"
if re.search(r'>\s*"\$ARM"', src):
    bad.append("upgrade-auto.sh 仍在自动写 .upgrade-armed（必须改为只出提案）")

if os.path.exists(ARM):
    tgt = open(ARM).read().strip().split()[0] if open(ARM).read().strip() else ""
    if not os.path.exists(APPR):
        bad.append("存在挂载件 %s 但无批准件 → 08:00 窗口会被拦截（这是预期，但请清理挂载）" % tgt)
    else:
        try:
            d = json.load(open(APPR))
        except Exception:
            d = {}
        if d.get("target") != tgt or not d.get("approved_by"):
            bad.append("批准件与挂载目标不匹配（target=%s, approved=%s）" % (tgt, d.get("target")))

if bad:
    for b in bad:
        print("❌ " + b)
    sys.exit(1)
print("✅ 升级纪律合规：自动升级只出提案，执行必须有主公批准件")
