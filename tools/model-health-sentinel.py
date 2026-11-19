#!/usr/bin/env python3
"""model-health-sentinel.py v1.0 (2026-11-17)
零 token 模型健康哨兵：只读网关 journal + 配置，不改任何配置、不发任何模型请求。
从真实流量里提取每个 provider/model 的失败（rate_limit / auth / timeout / 5xx），
落 state/model-health/status.json，状态变化时发飞书。

用法: python3 tools/model-health-sentinel.py [--minutes 60] [--quiet]
"""
import json, os, re, subprocess, sys, time, datetime

WS = "/home/j/.openclaw/workspace"
OUT = os.path.join(WS, "state/model-health/status.json")
CFG = "/home/j/.openclaw/openclaw.json"

def journal(minutes):
    try:
        return subprocess.run(
            ["journalctl", "--user", "-u", "openclaw-gateway",
             "--since", f"{minutes} min ago", "--no-pager"],
            capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        return ""

def referenced_models():
    """配置里所有被引用的 provider/model"""
    try:
        c = json.load(open(CFG, encoding="utf-8"))
    except Exception:
        return {}
    entries = (c.get("agents") or {}).get("entries") or {}
    dflt = ((c.get("agents") or {}).get("defaults") or {}).get("model") or {}
    use = {}
    for aid, v in entries.items():
        m = v.get("model") or {}
        prim = m.get("primary") or dflt.get("primary")
        if prim:
            use.setdefault(prim, []).append(aid)
        for f in (m.get("fallbacks") or []):
            use.setdefault(f, []).append(aid)
    if dflt.get("primary"):
        use.setdefault(dflt["primary"], []).append("(defaults)")
    return use

FIELD = re.compile(r'(\w+)=([^\s]+(?:\s(?!\w+=)[^\s]+)*)')

def parse_events(text):
    ev = []
    for line in text.splitlines():
        if "model fallback decision" not in line:
            continue
        body = line.split("model fallback decision:", 1)[1]
        d = {}
        for k in ("decision", "requested", "candidate", "reason", "next"):
            m = re.search(k + r"=([^\s]+)", body)
            if m:
                d[k] = m.group(1)
        if "detail=" in body:
            d["detail"] = body.split("detail=", 1)[1].strip()[:200]
        if d:
            ev.append(d)
    return ev

def classify(ev):
    reason = (ev.get("reason") or "").lower()
    detail = (ev.get("detail") or "").lower()
    if "rate_limit" in reason or "quota" in detail or "usage limit" in detail:
        return "rate_limit"
    if "auth" in reason or "401" in detail or "403" in detail:
        return "auth"
    if "timeout" in reason or "timed out" in detail:
        return "timeout"
    if "5" in (ev.get("detail") or "")[:3]:
        return "server"
    return reason or "other"

def main():
    args = sys.argv[1:]
    minutes = 60
    quiet = "--quiet" in args
    if "--minutes" in args:
        minutes = int(args[args.index("--minutes") + 1])
    text = journal(minutes)
    events = parse_events(text)
    use = referenced_models()

    stats = {}
    oks = {}
    for ev in events:
        model = ev.get("candidate") or ev.get("requested") or "?"
        decision = (ev.get("decision") or "").lower()
        if decision == "candidate_succeeded":
            oks[model] = oks.get(model, 0) + 1
            continue
        cls = classify(ev)
        s = stats.setdefault(model, {"fails": 0, "reasons": {}, "last_detail": ""})
        s["fails"] += 1
        s["reasons"][cls] = s["reasons"].get(cls, 0) + 1
        s["last_detail"] = ev.get("detail", "")[:200]

    now = time.time()
    models = {}
    for m in sorted(set(list(use.keys()) + list(stats.keys()))):
        s = stats.get(m, {"fails": 0, "reasons": {}, "last_detail": ""})
        hard = sum(v for k, v in s["reasons"].items() if k in ("rate_limit", "auth"))
        if hard >= 3:
            status = "down"
        elif s["fails"] >= 3:
            status = "degraded"
        elif s["fails"] > 0:
            status = "flaky"
        else:
            status = "ok"
        models[m] = {"status": status, "ok_window": oks.get(m, 0), "fails_window": s["fails"],
                     "reasons": s["reasons"], "agents": sorted(set(use.get(m, [])))[:40],
                     "last_detail": s["last_detail"]}

    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8")).get("models", {})
        except Exception:
            pass

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = {"generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "window_minutes": minutes, "models": models,
           "events_seen": len(events)}
    tmp = OUT + ".tmp"
    json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)

    changed = []
    for m, v in models.items():
        old = (prev.get(m) or {}).get("status", "ok")
        if v["status"] != old and v["status"] in ("down", "degraded"):
            changed.append((m, old, v))

    if changed and not quiet:
        lines = ["【模型哨兵】状态恶化 " + out["generated_at"]]
        for m, old, v in changed:
            lines.append(f"· {m}: {old} -> {v['status']}（{v['fails_window']} 次失败；{','.join(f'{k}×{n}' for k, n in v['reasons'].items())}）")
            if v["agents"]:
                lines.append("  受影响: " + ",".join(v["agents"][:8]) + ("…" if len(v["agents"]) > 8 else ""))
            if v["last_detail"]:
                lines.append("  最近原因: " + v["last_detail"][:120])
        subprocess.run(["bash", os.path.join(WS, "tools/notify.sh"), "\n".join(lines)],
                       capture_output=True, timeout=30)

    print(json.dumps({"generated_at": out["generated_at"], "events_seen": len(events),
                      "models": {k: v["status"] for k, v in models.items()},
                      "changed": [c[0] for c in changed]}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()

