#!/usr/bin/env python3
"""session-health-watch.py — 会话体积监控（只读 lcm.db，不锁库）

阈值（估算 token，取自 messages.token_count 求和）：
  > WARN(160000) → 告警（每会话 6 小时最多一次；高于 lossless 自动压缩线 150000，只在压缩没兜住时才响）
  > CRIT(180000) → 告警 + 自动 compact 该会话（同样 6 小时最多一次）

用法：
  python3 tools/session-health-watch.py            # 正常巡检，超标才输出
  python3 tools/session-health-watch.py --dry-run  # 只看，不动作
  python3 tools/session-health-watch.py --json     # 输出明细 JSON
"""
import json, os, sqlite3, subprocess, sys, time, datetime

W = os.path.expanduser("~/.openclaw/workspace")
DB = os.path.join(os.path.expanduser("~"), ".openclaw/lcm.db")
STATE = os.path.join(W, "state/session-health-state.json")
LOG = os.path.join(W, "state/session-health.log")
# 阈值按"当前上下文装载体积"标定（旧 60k/100k 是对历史累计调的，会虚高）
# 2026-10-17：与压缩策略对齐（lossless 大上下文阈值 20% ≈ 200k），避免预警和压缩互相打架
WARN = int(os.environ.get("SSW_WARN", "160000"))
CRIT = int(os.environ.get("SSW_CRIT", "180000"))
COOLDOWN = int(os.environ.get("SSW_COOLDOWN", str(6 * 3600)))
NOTIFY = os.path.join(W, "tools/notify.sh")
NOTIFY_STATE = os.path.join(W, "state/session-health-notify.json")
NOTIFY_COOLDOWN = int(os.environ.get("SSW_NOTIFY_COOLDOWN", "21600"))  # 同一批告警重复推送抑制：默认6小时

# ---- 存储/启动耗时监控（2026-11-01 主公批：并入本巡检，不新增定时任务）----
AGENTS_DIR = os.path.join(os.path.expanduser("~"), ".openclaw/agents")
STOR_AGENT_WARN_GB, STOR_AGENT_CRIT_GB = 1.0, 2.5   # 单个 agent 库体积
STOR_EV_WARN, STOR_EV_CRIT = 120000, 200000        # 单个 agent 事件数
STOR_TOTAL_WARN_GB, STOR_TOTAL_CRIT_GB = 5.0, 10.0  # 37 个 agent 库合计
STOR_LCM_WARN_GB, STOR_LCM_CRIT_GB = 1.0, 2.5      # lcm.db 体积
STARTUP_WARN_S, STARTUP_CRIT_S = 150, 210          # 网关启动耗时（当前基线 93~105s）
STARTUP_HIST = os.path.join(W, "state/startup-history.csv")


def _gb(n):
    return n / (1024.0 ** 3)


def check_storage():
    """各 agent 库体积/事件数 + lcm.db 体积。返回 [(标签, 级别, 明细)]。任何异常不外抛。"""
    try:
        return _check_storage_inner()
    except Exception as e:
        log(f"check_storage failed: {e}")
        return []


def _check_storage_inner():
    out = []
    total = 0.0
    per_db = []
    for path in sorted(glob_agent_dbs()):
        agent = path.split("/agents/")[-1].split("/")[0]
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        total += size
        per_db.append((agent, path, size))
    for agent, path, size in sorted(per_db, key=lambda x: -x[2]):
        g = _gb(size)
        if g >= STOR_AGENT_CRIT_GB:
            out.append((f"{agent} 库", "CRIT", f"{g:.2f}GB"))
        elif g >= STOR_AGENT_WARN_GB:
            out.append((f"{agent} 库", "WARN", f"{g:.2f}GB"))
        # 事件数只在库够大时才查，避免每轮 37 次全表计数
        if size >= 100 * 1024 * 1024:
            try:
                con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
                ev = con.execute("SELECT COUNT(*) FROM transcript_events").fetchone()[0]
                con.close()
                if ev >= STOR_EV_CRIT:
                    out.append((f"{agent} 事件数", "CRIT", f"{ev:,}"))
                elif ev >= STOR_EV_WARN:
                    out.append((f"{agent} 事件数", "WARN", f"{ev:,}"))
            except Exception as e:
                log(f"events count failed agent={agent}: {e}")
    tg = _gb(total)
    if tg >= STOR_TOTAL_CRIT_GB:
        out.append(("会话库合计", "CRIT", f"{tg:.2f}GB"))
    elif tg >= STOR_TOTAL_WARN_GB:
        out.append(("会话库合计", "WARN", f"{tg:.2f}GB"))
    try:
        lg = _gb(os.path.getsize(DB))
        if lg >= STOR_LCM_CRIT_GB:
            out.append(("lcm.db", "CRIT", f"{lg:.2f}GB"))
        elif lg >= STOR_LCM_WARN_GB:
            out.append(("lcm.db", "WARN", f"{lg:.2f}GB"))
    except OSError:
        pass
    return out


def glob_agent_dbs():
    import glob
    return glob.glob(os.path.join(AGENTS_DIR, "*", "agent", "openclaw-agent.sqlite"))


def check_startup(st):
    """网关每次重启只记一次启动耗时，写历史表；超阈值返回告警条目。"""
    try:
        r = subprocess.run(["systemctl", "--user", "show", "openclaw-gateway",
                            "-p", "ActiveEnterTimestamp", "--value"],
                           capture_output=True, text=True, timeout=15)
        ts = (r.stdout or "").strip()
    except Exception as e:
        log(f"startup check skipped: {e}")
        return []
    if not ts:
        return []
    b = st.setdefault("__startup__", {})
    if b.get("at") == ts:
        return []
    total_ms = 0.0
    try:
        j = subprocess.run(["journalctl", "--user", "-u", "openclaw-gateway",
                            "--since", ts, "--no-pager"],
                           capture_output=True, text=True, timeout=60)
        import re
        vals = [float(x) for x in re.findall(r"total=([0-9.]+)ms", j.stdout or "")]
        total_ms = max(vals) if vals else 0.0
    except Exception as e:
        log(f"startup journal read failed: {e}")
    b["at"] = ts
    b["total_s"] = round(total_ms / 1000.0, 1)
    try:
        new = not os.path.exists(STARTUP_HIST)
        os.makedirs(os.path.dirname(STARTUP_HIST), exist_ok=True)
        with open(STARTUP_HIST, "a", encoding="utf-8") as f:
            if new:
                f.write("booted_at,total_s\n")
            f.write(f"{ts},{b['total_s']}\n")
    except Exception as e:
        log(f"startup history write failed: {e}")
    if total_ms <= 0:
        return []
    sec = total_ms / 1000.0
    if sec >= STARTUP_CRIT_S:
        return [("启动耗时", "CRIT", f"{sec:.0f}s")]
    if sec >= STARTUP_WARN_S:
        return [("启动耗时", "WARN", f"{sec:.0f}s")]
    return []


def log(msg):
    line = f"[{datetime.datetime.now():%F %T}] {msg}"
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = f"{STATE}.{os.getpid()}.{int(time.time()*1000)}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)

def scan():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT c.conversation_id, c.session_key, c.updated_at,
               COUNT(CASE WHEN ci.item_type='message' THEN 1 END) AS msgs,
               COALESCE(SUM(CASE WHEN ci.item_type='message' THEN COALESCE(m.token_count,0) ELSE 0 END), 0)
             + COALESCE(SUM(CASE WHEN ci.item_type='summary' THEN COALESCE(s.token_count,0) ELSE 0 END), 0) AS tokens
        FROM conversations c
        JOIN context_items ci ON ci.conversation_id = c.conversation_id
        LEFT JOIN messages m ON m.message_id = ci.message_id
        LEFT JOIN summaries s ON s.summary_id = ci.summary_id
        WHERE c.active = 1
          AND c.updated_at >= datetime('now', '-7 days')
          AND c.session_key NOT LIKE '%:subagent:%'
          AND c.session_key NOT LIKE '%:cron:%'
          AND c.session_key NOT LIKE '%internal-session-effects%'
        GROUP BY c.conversation_id
        ORDER BY tokens DESC
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

def recently_used(updated_at, hours=48):
    """只有 48 小时内活跃过的会话才值得自动压缩（避免给死会话烧 token）。"""
    if not updated_at:
        return False
    try:
        dt = datetime.datetime.strptime(str(updated_at)[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False
    return (datetime.datetime.now() - dt).total_seconds() <= hours * 3600


def agent_of(session_key):
    # agent:<id>:...
    parts = session_key.split(":")
    return parts[1] if len(parts) > 2 else "main"

def notify(text):
    """推送并返回是否成功；失败不记账，下一轮会重推。"""
    try:
        r = subprocess.run(["bash", NOTIFY, text], timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            log(f"notify failed: rc={r.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        # 超时通常表示消息其实已发出、只是网关慢；按已送达记账，避免每轮重复轰炸
        log("notify timeout(90s): assumed delivered, fingerprint saved to stop duplicate storm")
        return True
    except Exception as e:
        log(f"notify failed: {e}")
        return False

def compact(session_key):
    agent = agent_of(session_key)
    cmd = ["openclaw", "sessions", "compact", session_key, "--agent", agent,
           "--timeout", "600000", "--json"]
    # 2026-10-17 双评审修正：原先 start_new_session 脱离父进程，在本机易被判为孤儿杀掉的
    # 后台进程，导致 CRIT 自动压缩从未真正执行。改为前台同步执行 + 全局互斥锁。
    import fcntl
    lock_path = os.path.join(W, "state", "session-compact.lock")
    try:
        lf = open(lock_path, "a+")
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        log(f"compact skipped (another compaction running) key={session_key}")
        return
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=480)
        log(f"compact done key={session_key} rc={r.returncode} out={(r.stdout or '')[:300]}")
    except subprocess.TimeoutExpired:
        log(f"compact timeout(480s) key={session_key}")
    except Exception as e:
        log(f"compact failed key={session_key}: {e}")
    finally:
        try:
            lf.close()
        except Exception:
            pass


def load_notify_state():
    try:
        with open(NOTIFY_STATE, encoding="utf-8") as f:
            ns = json.load(f)
        return ns if isinstance(ns, dict) else {}
    except Exception:
        return {}


def save_notify_state(d):
    try:
        os.makedirs(os.path.dirname(NOTIFY_STATE), exist_ok=True)
        tmp = NOTIFY_STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, NOTIFY_STATE)
    except Exception as e:
        log(f"notify state save failed: {e}")


def tok_bucket(tok):
    """token 分档（万），同会话持续暴涨即使不越级也要能再推一次。"""
    w = tok / 10000.0
    if w >= 12: return 12
    if w >= 9: return 9
    if w >= 6: return 6
    return 3

def alert_fingerprint(alerts):
    return ",".join(f"{k}:{lv}:{tok_bucket(t)}" for k, t, lv in sorted(alerts))

def main():
    dry = "--dry-run" in sys.argv
    as_json = "--json" in sys.argv
    now = time.time()
    st = load_state()
    rows = scan()
    alerts = []
    actions = []
    for r in rows:
        key = r["session_key"] or ""
        tok = int(r["tokens"] or 0)
        bucket = st.setdefault(key, {})
        if tok >= CRIT:
            last = bucket.get("crit_at", 0)
            alerts.append((key, tok, "CRIT"))
            fresh = recently_used(r.get("updated_at"))
            if now - last > COOLDOWN and fresh:
                if not dry:
                    compact(key)
                    actions.append(key)
                bucket["crit_at"] = now
        elif tok >= WARN:
            last = bucket.get("warn_at", 0)
            if now - last > COOLDOWN:
                alerts.append((key, tok, "WARN"))
                bucket["warn_at"] = now
    if not dry:
        save_state(st)
    storage = check_storage() + check_startup(st)
    if not dry and (storage or alerts):
        save_state(st)
    if as_json:
        print(json.dumps({"checked_at": datetime.datetime.now().isoformat(timespec="seconds"),
                          "sessions": rows, "alerts": [
                              {"key": k, "tokens": t, "level": lv} for k, t, lv in alerts],
                          "storage": [{"label": l, "level": lv, "detail": d} for l, lv, d in storage]},
                         ensure_ascii=False, indent=1))
        return
    for key, tok, lv in alerts:
        log(f"{lv} key={key} tokens≈{tok}")
    for l, lv, d in storage:
        log(f"{lv} {l}={d}")
    if alerts or storage:
        lines = []
        if alerts:
            lines.append(f"【会话体积告警】{len(alerts)} 个会话超过阈值（WARN={WARN} CRIT={CRIT}）")
            for key, tok, lv in alerts[:8]:
                act = "，已自动 compact" if (lv == "CRIT" and key in actions) else ""
                lines.append(f"· {key} ≈{tok//1000}K token（{lv}{act}）")
        if storage:
            lines.append(f"【存储/启动告警】{len(storage)} 项超阈值")
            for l, lv, d in storage[:10]:
                lines.append(f"· {l} {d}（{lv}）")
        msg = "\n".join(lines)
        print(msg)
        if not dry:
            fp = alert_fingerprint(alerts) + "|" + ",".join(f"{l}:{lv}" for l, lv, _ in storage)
            ns = load_notify_state()
            same = (fp == ns.get("fp")) and ((now - float(ns.get("at", 0) or 0)) < NOTIFY_COOLDOWN)
            if same:
                log(f"alert suppressed: same set, last pushed {int((now - float(ns.get('at', 0) or 0))/60)}min ago")
            else:
                if notify(msg):
                    save_notify_state({"fp": fp, "at": now})
                else:
                    log("notify failed; fingerprint not saved, will retry next run")

if __name__ == "__main__":
    main()
