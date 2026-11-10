#!/usr/bin/env python3
"""统一采集: 模型可用性 / 管家连通性 / key余额 / RPO日历 / 磁盘预测"""
import json, os, re, subprocess, sys, time, datetime

W = "/home/j/.openclaw/workspace"
ST = os.path.join(W, "state")
AUD = os.path.join(ST, "audit")
os.makedirs(AUD, exist_ok=True)
NOW = datetime.datetime.now()

def run(cmd, timeout=90):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or ""), int((time.time()-t0)*1000)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT", int((time.time()-t0)*1000)
    except Exception as e:
        return 1, str(e), int((time.time()-t0)*1000)

def models():
    out = []
    if os.environ.get("AUD_SKIP_MODELS"):
        prev = {}
        try:
            prev = {m["model"]: m for m in json.load(open(os.path.join(AUD, "collect.json")))["models"]}
        except Exception:
            pass
        for m, role in [("deepseek/deepseek-flash","主力"),("deepseek/deepseek-v4-pro","评审"),("zai/glm-5.3","评审/兜底")]:
            out.append(prev.get(m, {"model": m, "role": role, "ok": True, "ms": 0, "rc": 0, "cached": True}))
        return out
    targets = [
        ("deepseek/deepseek-flash", "主力"),
        ("deepseek/deepseek-v4-pro", "评审"),
        ("zai/glm-5.3", "评审/兜底"),
    ]
    for m, role in targets:
        rc, txt, ms = run("cd %s && timeout 70 openclaw infer model run --agent main --gateway --model %s --prompt 'reply OK only'" % (W, m), 90)
        ok = rc == 0 and "OK" in txt.upper()
        out.append({"model": m, "role": role, "ok": ok, "ms": ms, "rc": rc})
    return out

def agents():
    ap = os.path.join(AUD, "agents.json")
    if os.path.exists(ap):
        try:
            raw = json.load(open(ap))
            res = []
            for a in raw:
                ws = a.get("workspace") or ""
                res.append({"id": a.get("id"), "configured": True,
                            "workspace_ok": (not ws) or os.path.isdir(ws),
                            "model": a.get("model", "")})
            return res
        except Exception:
            pass
    rc, txt, _ = run("openclaw agents list --json", 60)
    res = []
    try:
        data = json.loads(txt[txt.index("{"):])
    except Exception:
        return [{"error": "agents list failed", "rc": rc}]
    items = data if isinstance(data, list) else (data.get("agents") or [])
    for a in items:
        if not isinstance(a, dict):
            continue
        aid = a.get("id") or "?"
        ws = a.get("workspace") or ""
        res.append({"id": aid, "configured": a.get("configured", True),
                    "workspace_ok": (not ws) or os.path.isdir(ws), "model": a.get("model", "")})
    return res

def agent_probe():
    if not os.environ.get("AUD_PROBE_AGENTS"):
        return []
    ap = os.path.join(AUD, "agents.json")
    raw = json.load(open(ap))
    out = []
    for a in raw:
        aid = a.get("id")
        rc, txt, ms = run("timeout 60 openclaw infer model run --agent %s --gateway --model %s --prompt 'reply OK only'" % (aid, a.get("model")), 75)
        out.append({"id": aid, "ok": rc == 0 and "OK" in txt.upper(), "ms": ms})
    return out

def keys():
    rc, txt, _ = run("cd %s && sh tools/ds-balance.sh" % W, 60)
    m = re.search(r"[¥$]\s*([0-9]+(?:\.[0-9]+)?)", txt)
    ds = float(m.group(1)) if m else None
    return {"deepseek_balance": ds, "raw_ok": rc == 0}

def rpo(days=14):
    bases = ["/mnt/d/openclaw-backups", "/mnt/e/openclaw-backups", "/mnt/h/openclaw-backups"]
    found = set()
    for base in bases:
        try:
            for n in os.listdir(base):
                for d in re.findall(r"(20\d\d)-(\d\d)-(\d\d)", n):
                    found.add("%s-%s-%s" % d)
        except Exception:
            continue
    today = NOW.date()
    cal = []
    for i in range(days):
        d = (today - datetime.timedelta(days=i)).isoformat()
        cal.append({"date": d, "ok": d in found})
    return {"days": cal, "gaps": [c["date"] for c in cal if not c["ok"]][:7]}

def disk():
    rc, txt, _ = run("df -P / /mnt/e /mnt/h /mnt/d 2>/dev/null", 30)
    rows = []
    for line in txt.splitlines()[1:]:
        f = line.split()
        if len(f) >= 6:
            rows.append({"mount": f[5], "pct": int(f[4].rstrip("%")), "avail": f[3]})
    return rows

def main():
    data = {"ts": NOW.isoformat(timespec="seconds"), "models": models(),
            "agents": agents(), "agent_probe": agent_probe(), "keys": keys(), "rpo": rpo(), "disk": disk()}
    p = os.path.join(AUD, "collect.json")
    with open(p, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    hist = os.path.join(ST, "disk-history.log")
    root = next((r for r in data["disk"] if r["mount"] == "/"), None)
    if root:
        with open(hist, "a") as f:
            f.write("%s %d %s\n" % (NOW.strftime("%Y-%m-%d"), root["pct"], root["avail"]))
    print(json.dumps({"ok": True, "out": p, "models_down": [m["model"] for m in data["models"] if not m["ok"]],
                      "agents": len(data["agents"]), "gaps": data["rpo"]["gaps"],
                      "balance": data["keys"]["deepseek_balance"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
