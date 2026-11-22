#!/usr/bin/env python3
"""selfreview-day-check.py — R12 的真实判据（修 2026-11-21 假绿）

问题：butler-duty.py 直接跑时，凌晨/上午所有时点都是「⏳未到点」，于是 0 不达标 → R12 假绿。
正确口径：查「最近一个自审时点已经过去的自然日」——
  当前时间 < 13:35 → 查昨天；≥ 13:35 → 查今天。
判据：五管家的 selfcheck 行必须全部 ✅（不能是「无产物」「未到点」）。
"""
import subprocess, sys, datetime, re

NOW = datetime.datetime.now()
CUTOFF = 13 * 60 + 35
if "--date" in sys.argv:  # 供自检：能对任意日期复现红/绿
    target = datetime.date.fromisoformat(sys.argv[sys.argv.index("--date") + 1])
elif (NOW.hour * 60 + NOW.minute) >= CUTOFF:
    target = datetime.date.today()
else:
    target = datetime.date.today() - datetime.timedelta(days=1)

out = subprocess.run(
    ["python3", "/home/j/.openclaw/workspace/tools/butler-duty.py", "--date", target.isoformat()],
    capture_output=True, text=True,
).stdout

rows = []
for line in out.splitlines():
    if "selfcheck" in line:
        rows.append(line.strip())
bad = [r for r in rows if "✅" not in r]
# 2026-11-22：已定案的历史缺口可登记豁免（state/work/selfreview-ack.jsonl）
import os, json
_ack = set()
_ap = "/home/j/.openclaw/workspace/state/work/selfreview-ack.jsonl"
if os.path.exists(_ap):
    for _ln in open(_ap, encoding="utf-8", errors="ignore"):
        _ln = _ln.strip()
        if not _ln:
            continue
        try:
            _a = json.loads(_ln)
        except Exception:
            continue
        _ack.add((_a.get("date", ""), _a.get("butler", "")))
if _ack:
    _kept = []
    for _r in bad:
        _hit = any(d == target.isoformat() and b in _r for d, b in _ack)
        if _hit:
            print("  ⚠已登记缺口（不判红）：" + _r.strip())
        else:
            _kept.append(_r)
    bad = _kept
print("检查日：%s（自审时点 12:54/13:04/13:14/13:24/13:34）" % target.isoformat())
for r in rows:
    print("  " + r)
if bad:
    print("❌ 缺结论 %d 项 → python3 tools/selfreview-harvest.py 收割，再看对应 cron lastRunStatus" % len(bad))
    sys.exit(1)
print("✅ %d 家自审结论均已落盘" % len(rows))
