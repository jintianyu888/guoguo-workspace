#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""butler-artifact-check.py — 各家自审「有没有真产物」核查（零 token）
rc=0 全部达标；rc=1 有缺失。判据：今日文件存在且 >=300 字节。
"""
import os, sys, datetime
today = datetime.date.today().isoformat()
WS = {"维护": "/home/j/openclaw-workspaces/maint", "备份": "/home/j/.openclaw/workspace-backup",
      "模型": "/home/j/.openclaw/workspace-model", "干活": "/home/j/openclaw-workspaces/work",
      "Hermess": "/home/j/openclaw-workspaces/sheet-music"}
CAND = [today + ".md", "self-review-" + today + ".md", today.replace("-", "") + ".md",
        "self-review-" + today.replace("-", "") + ".md"]
bad = []
for name, ws in WS.items():
    d = os.path.join(ws, "state/self-review")
    f = next((os.path.join(d, c) for c in CAND if os.path.exists(os.path.join(d, c))), None)
    if not f:
        bad.append("%s 无今日文件" % name); continue
    if os.path.getsize(f) < 800:
        bad.append("%s 文件过小(%dB<800)" % (name, os.path.getsize(f)))
if bad:
    print("；".join(bad)); sys.exit(1)
print("五家今日自审产物齐全")
