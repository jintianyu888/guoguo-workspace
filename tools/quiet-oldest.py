#!/usr/bin/env python3
# quiet-oldest.py —— 输出「最早一笔尚未被 resume 的 pause」距今分钟数；无则 0
import json, time, os, sys
p = "/home/j/.openclaw/workspace/state/backup-quiet/ledger.jsonl"
last = {}
if os.path.exists(p):
    for line in open(p, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("phase") not in (None, "done"):
            continue
        if not r.get("ok", True):
            continue
        a = r.get("action")
        if a in ("pause", "resume"):
            last[r.get("id")] = (a, r.get("ts"))
pending = [ts for a, ts in last.values() if a == "pause"]
if not pending:
    print(0)
    sys.exit(0)
oldest = min(pending)
try:
    t = time.mktime(time.strptime(oldest, "%Y-%m-%dT%H:%M:%S"))
except Exception:
    print(0)
    sys.exit(0)
print(int((time.time() - t) / 60))
