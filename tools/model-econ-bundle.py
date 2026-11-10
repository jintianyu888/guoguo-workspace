#!/usr/bin/env python3
"""model-econ-bundle.py v0.1 — 采集当日模型经济数据，供规划层使用（只读）"""
import json, os, subprocess, sys, csv
from datetime import datetime, timedelta

WS = "/home/j/.openclaw/workspace"
OUT_DIR = os.path.join(WS, "state/model-econ")
POLICY = os.path.join(OUT_DIR, "policy.json")
BURN = os.path.join(WS, "state/ds-burn.csv")
STATE = os.path.join(OUT_DIR, "glm-quota-state.json")

def load_json(p, default=None):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return default

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.now()
    today = now.strftime("%Y%m%d")
    bundle = {"date": today, "generated_at": now.isoformat(timespec="seconds")}

    # 余额：ds-burn.csv 最后一行
    bal = None
    try:
        with open(BURN) as f:
            rows = list(csv.reader(f))
        if rows:
            last = rows[-1]
            bal = {"ts": last[0], "balance": last[1]}
            bundle["burn_tail"] = rows[-8:]
    except Exception as e:
        bundle["burn_error"] = str(e)[:200]
    bundle["balance"] = bal

    # 默认模型（直读配置，不依赖 CLI）
    try:
        with open("/home/j/.openclaw/openclaw.json") as f:
            cfg = json.load(f)
        bundle["defaults_model"] = (cfg.get("agents") or {}).get("defaults", {}).get("model")
    except Exception as e:
        bundle["defaults_error"] = str(e)[:200]

    # cron 任务与模型覆盖
    try:
        p = subprocess.run(["timeout","120","openclaw","cron","list","--json"],
                           capture_output=True, text=True, timeout=130)
        d = json.loads(p.stdout)
        jobs = d.get("jobs", d) if isinstance(d, dict) else d
        items = []
        for j in jobs:
            items.append({
                "id": str(j.get("id",""))[:8],
                "name": j.get("name",""),
                "enabled": j.get("enabled"),
                "schedule": (j.get("schedule") or {}).get("expr") or (j.get("schedule") or {}).get("every") or (j.get("schedule") or {}).get("at"),
                "kind": (j.get("payload") or {}).get("kind",""),
                "model": j.get("model") or (j.get("payload") or {}).get("model"),
            })
        bundle["cron_total"] = len(items)
        bundle["cron_jobs"] = items
    except Exception as e:
        bundle["cron_error"] = str(e)[:300]

    bundle["policy"] = load_json(POLICY, {})
    bundle["glm_quota_state"] = load_json(STATE, {"tripped": False})
    bundle["quotas"] = load_json(os.path.join(OUT_DIR, "quotas.json"), {})

    out = os.path.join(OUT_DIR, f"bundle-{today}.json")
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out)
    print(out)

if __name__ == "__main__":
    sys.exit(main())
