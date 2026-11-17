#!/usr/bin/env python3
"""model-ledger.py v1.0 (2026-11-17) —— 模型统一账本（唯一真源）
一个 SQLite 管：模型能力 / 各家额度 / 优惠与到期 / 评测 / 路由 / 各 agent 分配 / 变更事件。

用法:
  python3 tools/model-ledger.py init
  python3 tools/model-ledger.py sync-config        # 从 openclaw.json 同步模型与分配
  python3 tools/model-ledger.py quota               # 从 quotas.json/balances.json 采集额度时序
  python3 tools/model-ledger.py promo-list [--due 14]
  python3 tools/model-ledger.py promo-add --id X --provider P --models a,b --type discount --desc "..." --expires 2026-12-01 --trigger "22:00后" --action "..."
  python3 tools/model-ledger.py eval-add --model M --task T --score 0.9 --samples 20 --repro "cmd"
  python3 tools/model-ledger.py route-list
  python3 tools/model-ledger.py route-set --activity heavy --primary M --fallbacks A,B --why "..."
  python3 tools/model-ledger.py report [--md]
  python3 tools/model-ledger.py doctor
"""
import argparse, json, os, sqlite3, sys, datetime

WS = "/home/j/.openclaw/workspace"
DB = os.path.join(WS, "state/model-econ/ledger.db")
CFG = "/home/j/.openclaw/openclaw.json"
QUO = os.path.join(WS, "state/model-econ/quotas.json")
BAL = os.path.join(WS, "state/model-econ/balances.json")
HEALTH = os.path.join(WS, "state/model-health/status.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS models(
  model TEXT PRIMARY KEY, provider TEXT, capabilities TEXT, ctx INTEGER,
  price TEXT, first_seen TEXT, last_seen TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS assignments(
  agent TEXT PRIMARY KEY, primary_model TEXT, fallbacks TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS quotas(
  ts TEXT, provider TEXT, model TEXT, kind TEXT, pct_remaining REAL, pct_used REAL, raw TEXT);
CREATE TABLE IF NOT EXISTS promos(
  id TEXT PRIMARY KEY, provider TEXT, models TEXT, type TEXT, desc TEXT,
  starts_at TEXT, expires_at TEXT, trigger TEXT, action TEXT, status TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS evals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT, task TEXT, score REAL, samples INTEGER,
  cost_cny REAL, latency_ms INTEGER, tested_at TEXT, repro TEXT, verdict TEXT);
CREATE TABLE IF NOT EXISTS routes(
  activity TEXT PRIMARY KEY, primary_model TEXT, fallbacks TEXT, why TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS events(
  ts TEXT, kind TEXT, subject TEXT, detail TEXT);
"""

def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    return c

def ev(c, kind, subject, detail=""):
    c.execute("INSERT INTO events VALUES(?,?,?,?)", (now(), kind, subject, detail[:500]))

def load(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return {}

def cmd_init(a):
    c = db(); ev(c, "init", "ledger", "schema created"); c.commit(); print("ok", DB)

def cmd_sync(a):
    c = db(); cfg = load(CFG)
    provs = (cfg.get("models") or {}).get("providers") or {}
    n_m = 0
    for pname, pv in provs.items():
        for m in (pv.get("models") or []):
            mid = f"{pname}/{m.get('id')}"
            caps = m.get("input") or ["text"]
            row = c.execute("SELECT first_seen FROM models WHERE model=?", (mid,)).fetchone()
            c.execute("""INSERT INTO models(model,provider,capabilities,ctx,price,first_seen,last_seen,source)
                         VALUES(?,?,?,?,?,?,?,?)
                         ON CONFLICT(model) DO UPDATE SET capabilities=excluded.capabilities,
                           ctx=excluded.ctx, price=excluded.price, last_seen=excluded.last_seen, source=excluded.source""",
                      (mid, pname, json.dumps(caps), m.get("contextWindow"),
                       json.dumps(m.get("cost") or {}), row[0] if row else now(), now(), "openclaw.json"))
            n_m += 1
    entries = (cfg.get("agents") or {}).get("entries") or {}
    dflt = ((cfg.get("agents") or {}).get("defaults") or {}).get("model") or {}
    n_a = 0
    for aid, v in entries.items():
        m = v.get("model") or {}
        prim = m.get("primary") or dflt.get("primary")
        c.execute("""INSERT INTO assignments(agent,primary_model,fallbacks,updated_at) VALUES(?,?,?,?)
                     ON CONFLICT(agent) DO UPDATE SET primary_model=excluded.primary_model,
                       fallbacks=excluded.fallbacks, updated_at=excluded.updated_at""",
                  (aid, prim, json.dumps(m.get("fallbacks") or []), now()))
        n_a += 1
    ev(c, "sync", "config", f"models={n_m} agents={n_a}")
    c.commit()
    print(f"同步完成：模型 {n_m} 个，agent 分配 {n_a} 条")

def cmd_quota(a):
    c = db(); q = load(QUO); b = load(BAL); ts = now(); n = 0
    for pname, e in ((q.get("providers") or {})).items():
        v = e.get("values") or {}
        rem = e.get("month_remaining_pct")
        used = e.get("month_used_pct")
        pct = None
        if isinstance(rem, (int, float)): pct = float(rem)
        elif isinstance(v.get("month_pct"), (int, float)): pct = float(v["month_pct"])
        kind = "month_remaining_pct" if pct is not None else "unknown"
        c.execute("INSERT INTO quotas VALUES(?,?,?,?,?,?,?)",
                  (e.get("captured_at") or ts, pname, "*", kind, pct,
                   float(used) if isinstance(used, (int, float)) else None,
                   json.dumps(v, ensure_ascii=False)[:800]))
        n += 1
    for pname, e in ((b.get("providers") or {})).items():
        money = e.get("money_cny") or e.get("wallet") or e.get("raw_balance")
        if isinstance(money, (int, float)):
            c.execute("INSERT INTO quotas VALUES(?,?,?,?,?,?,?)",
                      (e.get("captured_at") or ts, pname, "*", "balance_cny", None, None,
                       json.dumps({"money_cny": money}, ensure_ascii=False)))
            n += 1
    ev(c, "quota", "ingest", f"rows={n}")
    c.commit(); print(f"额度采集 {n} 条")

def cmd_promo_add(a):
    c = db()
    c.execute("""INSERT INTO promos(id,provider,models,type,desc,starts_at,expires_at,trigger,action,status,source)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET desc=excluded.desc, expires_at=excluded.expires_at,
                   trigger=excluded.trigger, action=excluded.action, status=excluded.status""",
              (a.id, a.provider, a.models, a.type, a.desc, a.starts_at or now(), a.expires,
               a.trigger, a.action, a.status or "active", a.source or "manual"))
    ev(c, "promo", a.id, a.desc); c.commit(); print("ok")

def cmd_promo_list(a):
    c = db(); due = getattr(a, "due", None)
    rows = c.execute("SELECT id,provider,type,desc,expires_at,trigger,action,status FROM promos ORDER BY expires_at").fetchall()
    today = datetime.date.today()
    shown = 0
    for r in rows:
        d = ""
        if r[4] and len(r[4]) >= 10:
            try:
                dd = datetime.date.fromisoformat(r[4][:10]); d = f" ({ (dd-today).days }天)"
                if due and (dd - today).days > due: continue
            except Exception: pass
        print(f"· {r[0]} [{r[2]}] {r[3]} 到期={r[4]}{d} 触发={r[5]} 动作={r[6]}")
        shown += 1
    print(f"共 {shown} 条")


PROMOS = os.path.join(WS, "state/model-econ/promos.json")

def cmd_promo_import(a):
    c = db(); d = load(PROMOS)
    n = 0
    for e in (d.get("entries") or []):
        c.execute("""INSERT INTO promos(id,provider,models,type,desc,starts_at,expires_at,trigger,action,status,source)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET provider=excluded.provider, models=excluded.models, type=excluded.type,
                       desc=excluded.desc, expires_at=excluded.expires_at, trigger=excluded.trigger,
                       action=excluded.action, status=COALESCE(promos.status,excluded.status)""",
                  (e.get("id"), e.get("provider"), json.dumps(e.get("models") or [], ensure_ascii=False),
                   e.get("type"), e.get("desc"), e.get("window"), e.get("expires_at"),
                   e.get("window") or "", e.get("action"), e.get("status") or "active", d.get("source")))
        n += 1
        # 套餐到期也作为 promos 的到期项存在
    ev(c, "promo", "import", f"rows={n}"); c.commit(); print(f"优惠导入 {n} 条")

def cmd_discover(a):
    """主动发现：刷新托管模型目录 + 与账本比对新增/下架"""
    import subprocess
    r = subprocess.run(["openclaw", "models", "refresh"], capture_output=True, text=True, timeout=180)
    print("models refresh rc=", r.returncode, (r.stdout or r.stderr or "").strip()[:200])
    c = db()
    before = {x[0] for x in c.execute("SELECT model FROM models")}
    cmd_sync(a)
    after_rows = c.execute("SELECT model, first_seen FROM models").fetchall()
    today = datetime.date.today().isoformat()
    new = [m for m, fs in after_rows if (fs or "")[:10] == today and m not in before]
    gone = sorted(before - {m for m, _ in after_rows})
    print("新增模型：" + (("、".join(new)) if new else "无"))
    print("已下架：" + (("、".join(gone)) if gone else "无"))
    if new:
        ev(c, "discover", "new_models", ",".join(new)); c.commit()

def cmd_eval_add(a):
    c = db()
    c.execute("""INSERT INTO evals(model,task,score,samples,cost_cny,latency_ms,tested_at,repro,verdict)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
              (a.model, a.task, a.score, a.samples, a.cost, a.latency, now(), a.repro, a.verdict))
    ev(c, "eval", a.model, f"{a.task} score={a.score}"); c.commit(); print("ok")

def cmd_eval_stale(a):
    c = db(); days = getattr(a, "days", 30)
    rows = c.execute("""SELECT model, MAX(tested_at) m FROM evals GROUP BY model""").fetchall()
    cut = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    for m, last in rows:
        if not last or last[:10] < cut: print(f"· {m} 最近评测 {last}（>={days} 天）")
    known = {r[0] for r in rows}
    for (m,) in c.execute("SELECT model FROM models").fetchall():
        if m not in known: print(f"· {m} 从未评测")

def cmd_route_set(a):
    c = db()
    c.execute("""INSERT INTO routes(activity,primary_model,fallbacks,why,updated_at) VALUES(?,?,?,?,?)
                 ON CONFLICT(activity) DO UPDATE SET primary_model=excluded.primary_model,
                   fallbacks=excluded.fallbacks, why=excluded.why, updated_at=excluded.updated_at""",
              (a.activity, a.primary, a.fallbacks or "[]", a.why, now()))
    ev(c, "route", a.activity, f"{a.primary}"); c.commit(); print("ok")

def cmd_route_list(a):
    c = db()
    for r in c.execute("SELECT activity,primary_model,fallbacks,why,updated_at FROM routes ORDER BY activity"):
        print(f"· {r[0]} → {r[1]}  备选={r[2]}  依据={r[3]}  ({r[4]})")

def build_report():
    c = db(); out = []
    today = datetime.date.today()
    out.append("【模型统一账本 · 日报 " + now() + "】")
    # 1 到期
    due = []
    for r in c.execute("SELECT id,desc,expires_at,action FROM promos WHERE status='active' ORDER BY expires_at"):
        if r[2] and len(r[2]) >= 10:
            try:
                d = datetime.date.fromisoformat(r[2][:10]); left = (d - today).days
                if left <= 14: due.append(f"· {r[1]}（{'已过期 '+str(-left)+' 天' if left < 0 else '剩 '+str(left)+' 天'}）→ {r[3]}")
            except Exception: pass
    out.append("① 优惠/额度到期：" + ("\n" + "\n".join(due) if due else " 14 天内无"))
    # 2 额度
    qs = []
    for r in c.execute("""SELECT provider, kind, pct_remaining FROM quotas WHERE ts=(SELECT MAX(ts) FROM quotas q2 WHERE q2.provider=quotas.provider AND q2.kind=quotas.kind)"""):
        if r[1] == "month_remaining_pct" and r[2] is not None: qs.append(f"· {r[0]} 剩余 {r[2]}%")
        elif r[1] == "balance_cny": qs.append(f"· {r[0]} 余额见 raw（无百分比）")
    out.append("② 额度：" + ("\n" + "\n".join(sorted(set(qs))) if qs else " 未采集"))
    # 3 集中度
    rows = c.execute("SELECT primary_model, COUNT(*) n FROM assignments GROUP BY primary_model ORDER BY n DESC").fetchall()
    tot = sum(r[1] for r in rows) or 1
    conc = [f"· {r[0]} {r[1]} 个（{round(100*r[1]/tot)}%）" for r in rows]
    out.append("③ 分配集中度：" + "\n" + "\n".join(conc))
    if rows and rows[0][1] / tot > 0.6:
        out.append(f"   ⚠ 风险：{rows[0][0]} 占 {round(100*rows[0][1]/tot)}%，单点故障会同时打死这些 agent")
    # 4 健康
    h = load(HEALTH).get("models") or {}
    bad = [f"· {m} = {v.get('status')}" for m, v in h.items() if v.get("status") in ("down", "degraded")]
    out.append("④ 模型健康：" + ("\n" + "\n".join(bad) if bad else " 全部 ok/flaky"))
    # 5 评测缺口
    ev_rows = dict(c.execute("SELECT model, MAX(tested_at) FROM evals GROUP BY model").fetchall())
    miss = []
    for (m,) in c.execute("SELECT model FROM models"):
        last = ev_rows.get(m)
        if not last: miss.append(m)
        elif last[:10] < (datetime.date.today() - datetime.timedelta(days=30)).isoformat(): miss.append(m + "(旧)")
    out.append("⑤ 评测缺口：" + ("\n· " + "\n· ".join(miss[:12]) if miss else " 无"))
    # 6 路由覆盖
    acts = [r[0] for r in c.execute("SELECT activity FROM routes")]
    out.append("⑥ 已定路由：" + (("、".join(acts)) if acts else " 空（需模型管家出方案）"))
    return "\n".join(out)

def cmd_report(a):
    txt = build_report()
    if getattr(a, "md", False):
        p = os.path.join(WS, "state/model-econ/report-latest.md")
        open(p, "w", encoding="utf-8").write(txt + "\n"); print("写入", p)
    print(txt)

def cmd_doctor(a):
    c = db(); issues = []
    # 配置 → 台账 一致性
    cfg = load(CFG); entries = (cfg.get("agents") or {}).get("entries") or {}
    led = dict(c.execute("SELECT agent, primary_model FROM assignments").fetchall())
    for aid, v in entries.items():
        prim = ((v.get("model") or {}).get("primary"))
        if prim and led.get(aid) != prim:
            issues.append(f"· {aid} 配置={prim} 台账={led.get(aid)}（跑 sync-config）")
    # 路由里的模型是否在库
    known = {r[0] for r in c.execute("SELECT model FROM models")}
    for act, prim in c.execute("SELECT activity, primary_model FROM routes"):
        if prim not in known: issues.append(f"· 路由 {act} 指向未登记模型 {prim}")
    # 路由首选的健康状态
    h = load(HEALTH).get("models") or {}
    for act, prim in c.execute("SELECT activity, primary_model FROM routes"):
        st = (h.get(prim) or {}).get("status")
        if st in ("down", "degraded"): issues.append(f"· 路由 {act} 首选 {prim} 当前 {st}")
    print("一致性检查：" + ("\n" + "\n".join(issues) if issues else " 通过"))

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    sub.add_parser("sync-config").set_defaults(fn=cmd_sync)
    sub.add_parser("quota").set_defaults(fn=cmd_quota)
    p = sub.add_parser("promo-add")
    for k in ("id", "provider", "models", "type", "desc", "starts_at", "expires", "trigger", "action", "status", "source"):
        p.add_argument("--" + k.replace("_", "-"), dest=k, default=None)
    p.set_defaults(fn=cmd_promo_add)
    p = sub.add_parser("promo-list"); p.add_argument("--due", type=int, default=None); p.set_defaults(fn=cmd_promo_list)
    p = sub.add_parser("eval-add")
    p.add_argument("--model"); p.add_argument("--task"); p.add_argument("--score", type=float)
    p.add_argument("--samples", type=int); p.add_argument("--cost", type=float); p.add_argument("--latency", type=int)
    p.add_argument("--repro"); p.add_argument("--verdict"); p.set_defaults(fn=cmd_eval_add)
    p = sub.add_parser("eval-stale"); p.add_argument("--days", type=int, default=30); p.set_defaults(fn=cmd_eval_stale)
    p = sub.add_parser("route-set")
    p.add_argument("--activity"); p.add_argument("--primary"); p.add_argument("--fallbacks"); p.add_argument("--why")
    p.set_defaults(fn=cmd_route_set)
    sub.add_parser("promo-import").set_defaults(fn=cmd_promo_import)
    sub.add_parser("discover").set_defaults(fn=cmd_discover)
    sub.add_parser("route-list").set_defaults(fn=cmd_route_list)
    p = sub.add_parser("report"); p.add_argument("--md", action="store_true"); p.set_defaults(fn=cmd_report)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    a = ap.parse_args(); a.fn(a)

if __name__ == "__main__":
    main()

