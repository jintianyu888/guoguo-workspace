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
    if os.path.isdir(d):
        for root, dirs, files in os.walk(d):
            depth = root[len(d):].count(os.sep)
            if depth >= 4:
                dirs[:] = []
                continue
            dirs[:] = [x for x in dirs if x not in ('.git', 'node_modules', '.history')]
            for f in files:
                if (D in f or D2 in f) and f.endswith('.md'):
                    p = os.path.join(root, f)
                    try:
                        if os.path.getsize(p) < 800:
                            continue
                    except OSError:
                        continue
                    best = p if not best or os.path.getsize(p) > os.path.getsize(best) else best
    if not best:
        bad.append("%s 无 %s 自审产物（>=800B，递归查 state/self-review 等子目录）" % (name, D))
        print("❌ %s" % bad[-1])
    else:
        print("✅ %s %s (%dB)" % (name, os.path.relpath(best, d), os.path.getsize(best)))
if bad:
    print("结论：FAIL %d 家缺产物" % len(bad)); sys.exit(1)
print("GREEN 五家自审产物齐全（%s）" % D); sys.exit(0)
