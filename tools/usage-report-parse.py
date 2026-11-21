#!/usr/bin/env python3
"""usage-report-parse.py —— 解析单日用量快照，打印人类可读摘要；纯读，零 token。"""
import json, sys, glob, os

def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None

cur = load(sys.argv[1])
if not cur:
    print("快照文件无法解析：" + sys.argv[1]); sys.exit(0)
agents = cur.get('agents') or {}
tot = cur.get('total_kb') or sum((v or {}).get('kb', 0) for v in agents.values())
ts = str(cur.get('ts', ''))
print("用量快照 %s（采集 %s）：总量 %.2f GB，事件 %s" % (
    cur.get('date'), ts[11:16] if len(ts) > 15 else '?', tot / 1048576, cur.get('total_events', 0)))
top = sorted(agents.items(), key=lambda kv: (kv[1] or {}).get('kb', 0), reverse=True)[:5]
if top:
    print("占用前 5：" + "，".join("%s %.2fG" % (k, (v or {}).get('kb', 0) / 1048576) for k, v in top))

d = cur.get('date', '')
prev = None
import datetime
try:
    dd = datetime.date.fromisoformat(d)
    for i in range(1, 4):
        p = os.path.join(os.path.dirname(sys.argv[1]), (dd - datetime.timedelta(days=i)).isoformat() + '.json')
        if os.path.exists(p):
            prev = load(p); break
except Exception:
    pass
if prev:
    delta = (cur.get('total_kb') or 0) - (prev.get('total_kb') or 0)
    print("对比 %s：%+.2f GB" % (prev.get('date'), delta / 1048576))
