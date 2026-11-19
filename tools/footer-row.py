#!/usr/bin/env python3
"""footer-row.py — 为页脚挑选「本会话」的用量单元格
用法：
  openclaw status 输出 | SKEY=<完整会话key> python3 tools/footer-row.py status
  curl -s :8899/api/state | SKEY=<完整会话key> python3 tools/footer-row.py api
设计要点（2026-10-24 双审意见）：
  * 绝不回退到 agent:main:main（已证实是另一条会话）
  * 只认 panel 给出的完整 session key；status 表里 key 被列宽截断，所以用「截断值必须是完整 key 的前缀」且唯一匹配
  * status 取不到时，退到 panel 精确匹配 totalTokens，此时缓存标记为未采集（不编造）
"""
import os, sys, re, json

key = os.environ.get("SKEY", "").strip()
mode = sys.argv[1] if len(sys.argv) > 1 else "status"
raw = sys.stdin.read()

if mode == "status":
    cands = []
    for line in raw.splitlines():
        if not line.startswith("│"):
            continue
        cells = [c.strip() for c in line.split("│")]
        if len(cells) < 8:
            continue
        cell_key = cells[1]
        if cell_key and len(cell_key) >= 15 and key.startswith(cell_key):
            cands.append((cell_key, cells[6]))
    if len(cands) == 1:
        print(cands[0][1])
    elif len(cands) > 1:
        # 多条都可前缀匹配 → 取截断最长者（最具体），仍不唯一则放弃
        best = max(len(c[0]) for c in cands)
        top = [c for c in cands if len(c[0]) == best]
        print(top[0][1] if len(top) == 1 else "")
else:
    try:
        d = json.loads(raw)
    except Exception:
        sys.exit(0)
    hit = [x for x in (d.get("activeSessions") or []) if x.get("key") == key]
    if len(hit) == 1 and isinstance(hit[0].get("totalTokens"), int):
        t = hit[0]["totalTokens"]
        print("%.0fk（缓存未采集）" % (t / 1000))
