#!/usr/bin/env bash
# R30：余额快照不得超过 45 分钟（model-status.py 由哨兵 15 分钟刷新）
set -u
python3 - <<'PY'
import json, os, sys, datetime
p="/home/j/.openclaw/workspace/state/model-econ/balances.json"
if not os.path.exists(p):
    print("FAIL 缺 balances.json"); sys.exit(1)
d=json.load(open(p)); ts=d.get("updated_at")
try:
    t=datetime.datetime.strptime(ts,"%Y-%m-%d %H:%M:%S")
except Exception:
    print("FAIL updated_at 无法解析:", ts); sys.exit(1)
age=(datetime.datetime.now()-t).total_seconds()/60
if age>45:
    print("FAIL 余额快照 %.0f 分钟未刷新（>45）→ systemctl --user start oc-model-sentinel.service" % age); sys.exit(1)
print("PASS R30 余额快照新鲜（%.0f 分钟前）" % age)
PY