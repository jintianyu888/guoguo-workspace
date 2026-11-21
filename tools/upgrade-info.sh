#!/bin/bash
# upgrade-info.sh —— 升级信息快照（给果果助手面板用，零 token）
# 写出 state/work/upgrade-info.json：当前版本 / 最新版本 / 最新发布天数 / 7天门槛 / 建议
set -uo pipefail
W=/home/j/.openclaw/workspace
OUT=$W/state/work/upgrade-info.json
NOWV=$(timeout 60 openclaw --version 2>/dev/null | tail -1 | awk '{print $2}')
J=$(timeout 200 python3 "$W/tools/oc-upgrade-check.py" --json 2>/dev/null)
python3 - "$NOWV" "$J" "$OUT" <<'PY'
import json, sys, time
nowv = sys.argv[1] or "未知"
try:
    d = json.loads(sys.argv[2])
except Exception:
    d = {}
latest = d.get("latest") or "未采集"
age = d.get("latest_age_days")
try:
    age = round(float(age), 1)
except Exception:
    age = None
gate = bool(age is not None and age >= 7)
rec = "已达 7 天门槛，可考虑升级" if gate else ("未满 7 天，建议再等" if age is not None else "取不到发布日期")
out = {
    "current": nowv,
    "latest": latest,
    "latest_age_days": age,
    "gate_ok": gate,
    "advice": rec,
    "decision_by": "主公",
    "updated": time.strftime("%F %T"),
}
json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
PY
