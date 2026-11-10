#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""model-ops.py — 模型经济唯一入口（2026-10-28 主公令：捏成一件事）

职责：额度 / 余额 / 价格 / 优惠 / 路由规划 / 评审池 / 健康，全部收敛到
       state/model-econ/econ.json 这一个真源，其它脚本只读它。

子命令：
  refresh [--scrape]   合并各采集器结果 → econ.json（--scrape 先跑抓取）
  plan                 计算路由、预算、跑道、告警，写入 econ.json 的 plan 段
  report [--md]        出唯一报表文本（信息窗/日报/看板都用这个）
  status               一行一家，快速核对
  verify               一致性校验，异常返回非 0
"""
import json, os, sys, time, subprocess, tempfile

WS = "/home/j/.openclaw/workspace"
E = os.path.join(WS, "state/model-econ")
ECON = os.path.join(E, "econ.json")
PROV = os.path.join(E, "provider-state.json")
BAL  = os.path.join(E, "balances.json")
QUO  = os.path.join(E, "quotas.json")
POL  = os.path.join(E, "policy.json")
POOL = os.path.join(E, "review-pool.json")
PRIC = os.path.join(E, "pricing-windows.json")
HIST = os.path.join(WS, "state/model-balance")

def now(): return time.strftime("%Y-%m-%dT%H:%M:%S%z")
def load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return {} if d is None else d
def atomic(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def pct(v):
    return round(float(v), 2) if isinstance(v, (int, float)) else None

def build():
    prov, bal, quo, pol = load(PROV), load(BAL), load(QUO), load(POL)
    pool = load(POOL); pric = load(PRIC)
    pv = prov.get("providers", {}); bv = bal.get("providers", {}); qv = quo.get("providers", {})
    out = {"schema": "econ/v1", "generated_at": now(), "providers": {}, "routing": {}, "derived": {}, "alerts": []}
    def _pct(blk, flat=None, used=None, limit=None):
        if isinstance(blk, dict):
            if isinstance(blk.get("pct"), (int, float)): return round(float(blk["pct"]), 2)
            u, l = blk.get("used"), blk.get("limit")
            if isinstance(u, (int, float)) and isinstance(l, (int, float)) and l: return round(u * 100.0 / l, 2)
        if isinstance(flat, (int, float)): return round(float(flat), 2)
        if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit:
            return round(used * 100.0 / limit, 2)
        return None

    ALIAS = {"zai": "zhipu"}
    merged = {}
    for n in sorted(set(pv) | set(bv) | set(qv)):
        k = ALIAS.get(n, n)
        merged.setdefault(k, []).append(n)
    names = sorted(merged)
    for n in names:
        srcs = merged[n]
        p = next((pv[x] for x in srcs if x in pv), {})
        b = next((bv[x] for x in srcs if x in bv), {})
        q = next((qv[x] for x in srcs if x in qv), {})
        kind = p.get("plan_kind") or ("payg" if n == "deepseek" else "subscription")
        month_blk = p.get("month") if isinstance(p.get("month"), dict) else {}
        money = None
        if kind == "payg":
            money = p.get("available") or b.get("balance") or b.get("available")
        else:
            money = b.get("wallet") or b.get("raw_balance") or b.get("topup_balance")
            if money in (0, 0.0): money = None
        e = {
            "kind": kind,
            "label": p.get("label") or b.get("label") or n,
            "plan": {"name": p.get("plan") or b.get("plan") or "", "expire": p.get("plan_expire") or "",
                     "auto_renew": b.get("auto_renew")},
            "quota": {
                "h5_pct": _pct(p.get("h5"), p.get("h5_pct") if p.get("h5_pct") is not None else b.get("h5_pct")),
                "week_pct": _pct(p.get("week"), p.get("week_pct") if p.get("week_pct") is not None else b.get("week_pct")),
                "month_pct": _pct(month_blk, p.get("month_used_pct") if p.get("month_used_pct") is not None else b.get("month_used_pct")),
                "week_reset": (p.get("week") or {}).get("reset_at") if isinstance(p.get("week"), dict) else b.get("week_reset_at"),
                "h5_reset": (p.get("h5") or {}).get("reset_at") if isinstance(p.get("h5"), dict) else b.get("h5_reset_at"),
            },
            "money_cny": money,
            "unit": "percent" if kind == "subscription" else "cny",
            "status": p.get("status") or b.get("status") or "unknown",
            "captured_at": p.get("captured_at") or b.get("captured_at") or q.get("captured_at"),
            "source": "provider-state" if p else ("balances" if b else "quotas"),
        }
        out["providers"][n] = e
    # 路由与评审池
    out["routing"] = {"default": "deepseek/deepseek-flash",
                      "fallbacks": pol.get("fallbacks") or [],
                      "review_pool": [{"vendor": v["vendor"], "model": v["model"]} for v in pool.get("vendors", [])],
                      "review_rule": pool.get("rule", "")}
    # 派生：日消耗与跑道
    hist = sorted(f for f in os.listdir(HIST) if f.endswith(".json"))[-8:] if os.path.isdir(HIST) else []
    series = []
    for f in hist:
        d = load(os.path.join(HIST, f)); v = d.get("balance_cny") or d.get("deepseek", {}).get("balance")
        if isinstance(v, (int, float)): series.append((f[:8], float(v)))
    burn = None
    if len(series) >= 2:
        days = max(1, len(series) - 1)
        burn = round((series[0][1] - series[-1][1]) / days, 2)
    ds = out["providers"].get("deepseek", {})
    runway = None
    if burn and burn > 0 and isinstance(ds.get("money_cny"), (int, float)):
        runway = round(ds["money_cny"] / burn, 1)
    out["derived"] = {"burn_cny_per_day": burn, "deepseek_runway_days": runway, "balance_series": series[-5:]}
    # 告警
    if runway is not None and runway <= 14:
        out["alerts"].append({"provider": "deepseek", "level": "warn",
                              "msg": f"DeepSeek 余额 ¥{ds['money_cny']:.2f}，按 ¥{burn}/天 约 {runway} 天见底"})
    for n, e in out["providers"].items():
        if e["kind"] == "subscription" and isinstance(e["quota"]["week_pct"], (int, float)) and e["quota"]["week_pct"] >= 90:
            out["alerts"].append({"provider": n, "level": "warn", "msg": f"{n} 本周额度已用 {e['quota']['week_pct']}%"})
        if not e["captured_at"]:
            out["alerts"].append({"provider": n, "level": "info", "msg": f"{n} 缺采集时间（禁止补零）"})
    if pric:
        out["pricing_window"] = pric
    return out

def fmt(e):
    if e["kind"] == "subscription":
        q = e["quota"]
        parts = []
        if q.get("h5_pct") is not None: parts.append(f"5h {q['h5_pct']}%")
        if q.get("week_pct") is not None: parts.append(f"周 {q['week_pct']}%")
        if q.get("month_pct") is not None: parts.append(f"本期 {q['month_pct']}%")
        return f"{e['label']}：" + ("，".join(parts) if parts else "额度未采集") 
    return f"{e['label']}：¥{e['money_cny']:.2f}" if isinstance(e.get("money_cny"), (int, float)) else f"{e['label']}：余额未采集"

def cmd_report(md=False):
    d = build()
    L = []
    L.append(f"== 模型经济总表 {d['generated_at']} ==")
    for n, e in d["providers"].items(): L.append("  " + fmt(e))
    dv = d["derived"]
    if dv.get("burn_cny_per_day") is not None:
        L.append(f"  日耗 ≈ ¥{dv['burn_cny_per_day']}　DeepSeek 跑道 ≈ {dv['deepseek_runway_days']} 天")
    if d["routing"]["review_pool"]:
        L.append("  评审池：" + " / ".join(p["model"] for p in d["routing"]["review_pool"]))
    for a in d["alerts"]: L.append(f"  ⚠️ {a['msg']}")
    return "\n".join(L)

def cmd_status():
    d = load(ECON) or build()
    for n, e in d.get("providers", {}).items(): print(fmt(e))
    dv = d.get("derived", {})
    if dv.get("deepseek_runway_days") is not None: print(f"跑道 {dv['deepseek_runway_days']} 天 / 日耗 ¥{dv.get('burn_cny_per_day')}")

def cmd_verify():
    d = load(ECON)
    bad = []
    if not d: bad.append("econ.json 不存在，先 refresh")
    for n, e in (d.get("providers") or {}).items():
        if e.get("kind") == "subscription" and e.get("money_cny") not in (None,) and "月" in str(e.get("unit")):
            bad.append(f"{n} 订阅制出现金额口径")
        if e.get("money_cny") == 0: bad.append(f"{n} 余额为 0（禁止零兜底）")
        if not e.get("captured_at"): bad.append(f"{n} 缺 captured_at")
    for b in bad: print("FAIL", b)
    print("OK" if not bad else f"共 {len(bad)} 项问题")
    return 0 if not bad else 1

def cmd_refresh(scrape=False):
    if scrape:
        for s in ("tools/quota-scrape.py", "tools/quota-reconcile.py"):
            p = os.path.join(WS, s)
            args = ["--run"] if s.endswith("quota-scrape.py") else []
            if os.path.exists(p):
                print(f"[scrape] {s} {' '.join(args)}".rstrip())
                subprocess.run([sys.executable, p] + args, cwd=WS, timeout=900)
    d = build(); atomic(ECON, d)
    print(f"econ.json 已更新：{len(d['providers'])} 家，告警 {len(d['alerts'])} 条")
    return 0

if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "report"
    if cmd == "refresh": sys.exit(cmd_refresh("--scrape" in a))
    if cmd == "report": print(cmd_report("--md" in a)); sys.exit(0)
    if cmd == "status": cmd_status(); sys.exit(0)
    if cmd == "verify": sys.exit(cmd_verify())
    if cmd == "plan":
        d = build(); atomic(ECON, d); print(cmd_report()); sys.exit(0)
    print(__doc__); sys.exit(2)
