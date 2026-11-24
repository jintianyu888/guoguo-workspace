#!/usr/bin/env python3
"""job-ledger.py — 全部定时任务（cron）的唯一运行账本（2026-11-21 主公令）

背景：100 个任务各自往 state/work/*.log 里写，查「这个任务跑没跑、成没成」得翻十几处。
现在统一进 state/ledger/jobs.db：
  jobs(job_id PK, name, agent, enabled, schedule, updated)
  runs(receipt_id PK, job_id, name, agent, status, started, finished, seconds, error)
数据源：OpenClaw cron 运行回执（openclaw.sqlite 的 cron_run_receipts）+ /home/j/.openclaw/cron/jobs.json
用法：
  job-ledger.py sync                 # 增量同步（幂等）
  job-ledger.py report [hours]       # 近 N 小时：跑了几次/失败几次/哪些任务没跑
  job-ledger.py job <关键词>          # 某任务最近运行
  job-ledger.py coverage             # 覆盖体检：有账的任务占比
"""
import argparse, json, os, shutil, sqlite3, sys, time

WS = "/home/j/.openclaw/workspace"
DB = WS + "/state/ledger/jobs.db"
OCDB = "/home/j/.openclaw/state/openclaw.sqlite"
JOBS = "/home/j/.openclaw/cron/jobs.json"
TMP = "/tmp/oc-jobs-ledger.sqlite"


def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, name TEXT, agent TEXT,
      enabled INTEGER, schedule TEXT, updated TEXT);
    CREATE TABLE IF NOT EXISTS runs(receipt_id TEXT PRIMARY KEY, job_id TEXT, name TEXT,
      agent TEXT, status TEXT, started TEXT, finished TEXT, seconds REAL, error TEXT);
    CREATE INDEX IF NOT EXISTS idx_runs_job ON runs(job_id, started);
    """)
    return c


def sched(s):
    if not s:
        return ""
    k = s.get("kind")
    if k == "every":
        ms = s.get("everyMs") or 0
        return "every %dm" % round(ms / 60000) if ms >= 60000 else "every %ds" % round(ms / 1000)
    if k == "cron":
        return "cron %s" % s.get("expr", "")
    if k == "at":
        return "at"
    return json.dumps(s, ensure_ascii=False)[:40]


def ts(ms):
    return time.strftime("%F %T", time.localtime(ms / 1000)) if ms else None


def sync():
    c = conn()
    # 1) 任务元数据
    n_jobs = 0
    n_runs = 0
    if os.path.exists(OCDB):
        shutil.copyfile(OCDB, TMP)
        o = sqlite3.connect(TMP)
        # 1) 任务元数据来自 cron_jobs（jobs.json 在新版已不存在）
        try:
            jrows = o.execute("SELECT job_id,name,agent_id,enabled,job_json FROM cron_jobs").fetchall()
        except sqlite3.Error:
            jrows = []
        for jid, nm, ag, en, jj in jrows:
            try:
                sch = json.loads(jj).get("schedule")
            except Exception:
                sch = None
            c.execute("INSERT INTO jobs(job_id,name,agent,enabled,schedule,updated) VALUES(?,?,?,?,?,?) "
                      "ON CONFLICT(job_id) DO UPDATE SET name=excluded.name,agent=excluded.agent,"
                      "enabled=excluded.enabled,schedule=excluded.schedule,updated=excluded.updated",
                      (jid, nm, ag or "", en, sched(sch), time.strftime("%F %T")))
            n_jobs += 1
        # 2) 运行回执
        try:
            rows = o.execute("SELECT receipt_id,job_id,agent_id,status,started_at_ms,finished_at_ms,error_text "
                             "FROM cron_run_receipts").fetchall()
        except sqlite3.Error as e:
            print("读回执失败:", e)
            rows = []
        o.close()
        names = dict(c.execute("SELECT job_id,name FROM jobs").fetchall())
        for r in rows:
            dur = round((r[5] - r[4]) / 1000, 1) if r[5] and r[4] else None
            cur = c.execute("INSERT INTO runs(receipt_id,job_id,name,agent,status,started,finished,seconds,error) "
                            "VALUES(?,?,?,?,?,?,?,?,?) "
                            "ON CONFLICT(receipt_id) DO UPDATE SET status=excluded.status, finished=excluded.finished,"
                            " seconds=excluded.seconds, error=excluded.error, name=coalesce(excluded.name,runs.name) "
                            "WHERE runs.status='running' OR excluded.status!='running'",
                            (r[0], r[1], names.get(r[1]), r[2], r[3], ts(r[4]), ts(r[5]), dur, (r[6] or "")[:300]))
            n_runs += cur.rowcount
    # 2.5) 已从 cron 删除的任务，标记停用（保留历史回执）
    live = [j[0] for j in jrows]
    if live:
        c.execute("UPDATE jobs SET enabled=0 WHERE job_id NOT IN (%s)" % ",".join("?" * len(live)), live)
    # 3) 补名（历史回执先入库时还没有任务元数据）
    c.execute("UPDATE runs SET name=(SELECT j.name FROM jobs j WHERE j.job_id=runs.job_id) WHERE name IS NULL")
    c.commit()
    print("同步完成：任务 %d 条，新增运行记录 %d 条" % (n_jobs, n_runs))


    # 2026-11-22：收尾孤儿记录（进程被重启/静默窗打断时，起过但永远收不了尾）
    try:
        import time as _t
        cutoff=_t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(_t.time()-7200))
        cur=c.execute("update runs set status='orphaned', error=coalesce(nullif(error,''),'未收尾：进程被中断，无结束记录') where status='running' and started < ?", (cutoff,))
        c.commit()
        if cur.rowcount: print("孤儿收尾: %d 条"%cur.rowcount)
    except Exception as e:
        print("孤儿收尾失败:", e)

def classify(status, err):
    e = (err or "").lower()
    if status == "ok":
        return "ok"
    if status == "skipped":
        return "skip"
    if "gateway stopping" in e or "cancelled" in e or "quiet" in e:
        return "env"
    if "timed out" in e or "timeout" in e:
        return "timeout"
    return "fail"


def report(hours):
    c = conn()
    since = time.strftime("%F %T", time.localtime(time.time() - hours * 3600))
    rows = c.execute("SELECT status, error FROM runs WHERE started>=?", (since,)).fetchall()
    b = {"ok": 0, "skip": 0, "env": 0, "timeout": 0, "fail": 0}
    for st, er in rows:
        b[classify(st, er)] += 1
    print("近 %d 小时：共 %d 次 | 成功 %d｜跳过 %d｜环境中断 %d｜超时 %d｜真失败 %d"
          % (hours, len(rows), b["ok"], b["skip"], b["env"], b["timeout"], b["fail"]))
    bad = c.execute("SELECT name,status,error,count(*),max(started) FROM runs WHERE started>=? AND status!='ok' "
                    "GROUP BY name,status,substr(ifnull(error,''),1,40) ORDER BY count(*) DESC LIMIT 8", (since,)).fetchall()
    for nm, st, er, n, last in bad:
        k = classify(st, er)
        if k in ("ok", "skip"):
            continue
        print("  %s %-26s %2d 次 最近 %s | %s" % ({"env": "⏸", "timeout": "⏱", "fail": "❌"}[k], (nm or "?")[:26], n, last, (er or "")[:40]))


def prev_slot(sch, before_ts):
    """最近一次「应跑时刻」（<= before_ts）"""
    if not sch:
        return None
    import datetime, re
    if sch.startswith("every"):
        m = re.match(r"every (\d+)([ms])", sch)
        if not m:
            return None
        per = int(m.group(1)) * (60 if m.group(2) == "m" else 1)
        return before_ts - (before_ts % per)
    if not sch.startswith("cron"):
        return None
    f = sch.split(" ", 1)[1].strip().split()
    if len(f) != 5:
        return None
    t = datetime.datetime.fromtimestamp(before_ts).replace(second=0, microsecond=0)
    for _ in range(0, 60 * 24 * 40):
        if (_match(f[0], t.minute) and _match(f[1], t.hour) and _match(f[2], t.day)
                and _match(f[3], t.month) and _match(f[4], t.isoweekday() % 7)):
            return t.timestamp()
        t -= datetime.timedelta(minutes=1)
    return None


def missed(hours=24, quiet=False):
    """排程该跑却没跑：最近一次应跑时刻（提前 2h 宽限）之后没有任何运行记录"""
    c = conn()
    now = time.time()
    grace = 2 * 3600
    rows = c.execute("SELECT job_id,name,schedule FROM jobs WHERE enabled=1").fetchall()
    out = []
    ack=set()
    ap=os.path.join(WS,"state/work/job-miss-ack.jsonl")
    if os.path.exists(ap):
        for ln in open(ap,encoding="utf-8",errors="ignore"):
            ln=ln.strip()
            if not ln: continue
            try: a=json.loads(ln)
            except Exception: continue
            ack.add((a.get("name",""), a.get("slot","")))
    for jid, nm, sch in rows:
        slot = prev_slot(sch, now - grace)
        if not slot:
            continue
        slot_s = time.strftime("%F %T", time.localtime(slot))
        cnt = c.execute("SELECT count(*) FROM runs WHERE job_id=? AND started>=?",
                        (jid, time.strftime("%F %T", time.localtime(slot - 5400)))).fetchone()[0]
        if cnt == 0:
            slot_lbl = time.strftime("%m-%d %H:%M", time.localtime(slot))
            if (nm, slot_lbl) in ack:
                continue
            out.append((nm, slot_lbl))
    if quiet:
        return out
    if out:
        print("该跑没跑（%d 个）：" % len(out))
        for nm, slot in out:
            print("   ⚠ %-30s 应跑 %s，之后无记录" % (nm[:30], slot))
    else:
        print("所有任务在最近一次应跑时刻后都有运行记录")
    return out


def _match(field, val):
    if field == "*":
        return True
    for part in field.split(","):
        if "/" in part:
            base, step = part.split("/")
            step = int(step)
            if base == "*":
                if val % step == 0:
                    return True
            elif "-" in base:
                a, b = base.split("-")
                if int(a) <= val <= int(b) and (val - int(a)) % step == 0:
                    return True
            elif val == int(base):
                return True
        elif "-" in part:
            a, b = part.split("-")
            if int(a) <= val <= int(b):
                return True
        else:
            if int(part) == val:
                return True
    return False


def expected_count(sch, start_ts, now_ts):
    if not sch:
        return 0
    if sch.startswith("every"):
        import re
        m = re.match(r"every (\d+)([ms])", sch)
        if not m:
            return 0
        per = int(m.group(1)) * (60 if m.group(2) == "m" else 1)
        return int((now_ts - start_ts) / per)
    if not sch.startswith("cron"):
        return 0
    expr = sch.split(" ", 1)[1].strip()
    f = expr.split()
    if len(f) != 5:
        return 0
    import datetime
    t = datetime.datetime.fromtimestamp(start_ts).replace(second=0, microsecond=0)
    end = datetime.datetime.fromtimestamp(now_ts)
    n = 0
    while t <= end:
        if (_match(f[0], t.minute) and _match(f[1], t.hour) and _match(f[2], t.day)
                and _match(f[3], t.month) and _match(f[4], t.isoweekday() % 7)):
            n += 1
        t += datetime.timedelta(minutes=1)
    return n


def job(kw):
    c = conn()
    for r in c.execute("SELECT name,job_id FROM jobs WHERE name LIKE ? OR job_id LIKE ?", ("%" + kw + "%", "%" + kw + "%")):
        print("== %s (%s)" % (r[0], r[1]))
        for x in c.execute("SELECT started,status,seconds,error FROM runs WHERE job_id=? ORDER BY started DESC LIMIT 5", (r[1],)):
            print("   %s %-4s %ss %s" % (x[0], x[1], x[2] if x[2] is not None else "?", (x[3] or "")[:80]))


def coverage():
    c = conn()
    en = c.execute("SELECT count(*) FROM jobs WHERE enabled=1").fetchone()[0]
    withruns = c.execute("SELECT count(DISTINCT r.job_id) FROM runs r JOIN jobs j ON j.job_id=r.job_id "
                         "WHERE j.enabled=1").fetchone()[0]
    print("启用任务 %d，有运行记录 %d（%.0f%%）" % (en, withruns, 100.0 * withruns / en if en else 0))
    return 0 if en and withruns / en >= 0.9 else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("sync")
    rp = s.add_parser("report"); rp.add_argument("hours", nargs="?", type=int, default=24)
    jp = s.add_parser("job"); jp.add_argument("kw")
    mp = s.add_parser("missed"); mp.add_argument("hours", nargs="?", type=int, default=24)
    mp.add_argument("--quiet", action="store_true")
    s.add_parser("coverage")
    a = p.parse_args()
    if a.cmd == "sync":
        sync()
    elif a.cmd == "report":
        report(a.hours)
    elif a.cmd == "job":
        job(a.kw)
    elif a.cmd == "missed":
        r = missed(a.hours, a.quiet)
        if a.quiet:
            sys.exit(1 if r else 0)
    else:
        sys.exit(coverage())
