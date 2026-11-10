#!/usr/bin/env python3
"""agent-freeze.py — 管家空闲冻结机制（主公 2026-11-06 令）

规则：连续 7 天无任何会话活动 → 冻结；被调用或手动解冻 → 立即恢复。
冻结动作：记档 state/agents-frozen.json + 记录其定时任务（不删、不改配置、不动工作区）。
白名单永不冻结：main / maint / backup / model / work / print。

用法：
  agent-freeze.py                 # 只读报告（默认）
  agent-freeze.py --apply         # 实际冻结到期管家
  agent-freeze.py --unfreeze ID   # 解冻
  agent-freeze.py --json          # 机器可读
"""
import json, os, shutil, sqlite3, subprocess, sys, time, datetime

WS = "/home/j/.openclaw/workspace"
DB = "/home/j/.openclaw/state/openclaw.sqlite"
STATE = os.path.join(WS, "state/agents-frozen.json")
DAYS = 7
WHITELIST = {"main", "maint", "backup", "model", "work", "print"}


def openclaw_bin():
    """cron 环境 PATH 只有 /usr/bin:/bin，裸 openclaw 必然找不到（2026-11-09 修）"""
    cands = [shutil.which("openclaw"), os.path.expanduser("~/.npm-global/bin/openclaw"),
             "/home/j/.openclaw/tmp/agent-cli/openclaw", "/usr/local/bin/openclaw"]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return "openclaw"
NOW = time.time()


def load_registry():
    try:
        return json.load(open("/home/j/.openclaw/state/agents-registry.json"))
    except Exception:
        return {}


def last_activity():
    out = {}
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        for aid, ts in c.execute(
            "select agent_id, max(updated_at) from session_state_heads group by agent_id"
        ):
            if ts is None:
                continue
            ts = float(ts)
            if ts > 1e12:
                ts /= 1000.0
            out[str(aid)] = max(out.get(str(aid), 0), ts)
    except Exception as e:
        print("warn: 读会话库失败 %s" % e, file=sys.stderr)
    return out


def all_agents():
    ids = set(load_registry().keys())
    base = "/home/j/.openclaw/agents"
    if os.path.isdir(base):
        ids |= {d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))}
    return sorted(ids)


def cron_agents():
    out = {}
    try:
        r = subprocess.run([openclaw_bin(), "cron", "list", "--json"],
                           capture_output=True, text=True, timeout=120)
        data = json.loads(r.stdout or "{}")
        jobs = data.get("jobs") or data.get("items") or []
        for j in jobs:
            a = j.get("agentId") or j.get("agent") or ""
            if a:
                out.setdefault(a, []).append(j.get("id") or j.get("jobId"))
    except Exception as e:
        print("warn: 读 cron 失败 %s" % e, file=sys.stderr)
    return out


def frozen_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"frozen": {}, "updated_at": None}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    st["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def fmt(ts):
    if not ts:
        return "从未使用"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def main():
    argv = sys.argv[1:]
    act = last_activity()
    agents = all_agents()
    cron = cron_agents()
    st = frozen_state()

    if "--unfreeze" in argv:
        aid = argv[argv.index("--unfreeze") + 1]
        rec = st["frozen"].pop(aid, None)
        save_state(st)
        print("已解冻 %s%s" % (aid, "（原冻结 %s）" % rec.get("at") if rec else "（本未冻结）"))
        return 0

    # 有激活自动解冻：冻结后又有会话活动 → 立即恢复
    auto_back = []
    for a, rec in list(st["frozen"].items()):
        try:
            fat = datetime.datetime.strptime(rec.get("at", ""), "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            continue
        if act.get(a, 0) > fat:
            st["frozen"].pop(a, None)
            auto_back.append(a)
    if auto_back:
        save_state(st)

    rows = []
    for a in agents:
        ts = act.get(a, 0)
        days = (NOW - ts) / 86400 if ts else 9999
        rows.append({"agent": a, "last": fmt(ts), "idle_days": round(days, 1),
                     "cron_jobs": len(cron.get(a, [])), "whitelisted": a in WHITELIST,
                     "frozen": a in st["frozen"]})
    rows.sort(key=lambda r: r["idle_days"], reverse=True)
    cand = [r for r in rows if r["idle_days"] >= DAYS and not r["whitelisted"] and not r["frozen"]]
    # 有定时任务的管家可能承担职责，不自动冻结，单列待主公确认
    due = [r for r in cand if r["cron_jobs"] == 0]
    need_confirm = [r for r in cand if r["cron_jobs"] > 0]

    if "--json" in argv:
        print(json.dumps({"threshold_days": DAYS, "due": due, "all": rows}, ensure_ascii=False, indent=1))
        return 0

    if auto_back:
        print("自动解冻 %d 个（检测到新活动）：%s" % (len(auto_back), ",".join(sorted(auto_back))))
    print("冻结阈值 %d 天 | 白名单 %s" % (DAYS, ",".join(sorted(WHITELIST))))
    print("可自动冻结（无定时任务）%d 个：" % len(due))
    for r in due:
        print("  %-14s 空闲 %5.1fd  %s" % (r["agent"], r["idle_days"], r["last"]))
    if need_confirm:
        print("需主公确认（有定时任务）%d 个：" % len(need_confirm))
        for r in need_confirm:
            print("  %-14s 空闲 %5.1fd  任务%d个  %s" % (r["agent"], r["idle_days"], r["cron_jobs"], r["last"]))
    if "--apply" in argv:
        for r in due:
            st["frozen"][r["agent"]] = {"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "idle_days": r["idle_days"], "last_activity": r["last"],
                                        "cron_jobs": cron.get(r["agent"], [])}
        save_state(st)
        print("已冻结 %d 个，记录 %s" % (len(due), STATE))
    elif due:
        print("（只读报告；加 --apply 执行冻结）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
