#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""butler-artifact-check.py v2 (2026-11-22) — 五大管家自审产物核查（零 token）
自审在 12:25-13:35 之间跑，此前查「今天」必然报红。故按参考日：
  当前时间 >= 13:35 → 查今天；否则查昨天。
判据：参考日文件存在且 >= 800 字节。rc=0 达标，rc=1 有缺失。
"""
import os, sys, datetime

now = datetime.datetime.now()
REF = now.date() if now.strftime("%H:%M") >= "13:35" else now.date() - datetime.timedelta(days=1)
D = REF.isoformat()
D2 = D.replace("-", "")

WS = {
    "维护": "/home/j/openclaw-workspaces/maint",
    "备份": "/home/j/.openclaw/workspace-backup",
    "模型": "/home/j/.openclaw/workspace-model",
    "干活": "/home/j/openclaw-workspaces/work",
    "Hermess": "/home/j/openclaw-workspaces/sheet-music",
}
CAND = [D + ".md", "self-review-" + D + ".md", D2 + ".md", "selfcheck-" + D + ".md", "selfcheck-" + D2 + ".md"]

bad = []
for name, d in WS.items():
    best = None
    for c in CAND:
        p = os.path.join(d, c)
        if os.path.exists(p):
            best = p if not best or os.path.getsize(p) > os.path.getsize(best) else best
    if not best:
        cands = []
        if os.path.isdir(d):
            for f in os.listdir(d):
                if REF.isoformat() in f or D2 in f:
                    cands.append(os.path.join(d, f))
        best = max(cands, key=os.path.getsize) if cands else None
    if not best:
        bad.append("%s 无 %s 自审产物" % (name, D))
        continue
    if os.path.getsize(best) < 800:
        bad.append("%s 产物过小(%dB<800)" % (name, os.path.getsize(best)))
if bad:
    print("参考日 %s：" % D + "；".join(bad))
    sys.exit(1)
print("参考日 %s：五家自审产物齐全（>=800B）" % D)
