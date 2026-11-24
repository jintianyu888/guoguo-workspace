#!/usr/bin/env python3
"""fail-rca.py —— 失败必复盘（R34）入口：零 token
用法：
  python3 tools/fail-rca.py check [--hours 48]     # 列出近 N 小时失败但没有复盘记录的任务，有未覆盖则 rc=1
  python3 tools/fail-rca.py add <任务名> --sig "错误特征" --cause "根因" --fix "修法" --status fixed|monitoring|blocked
  python3 tools/fail-rca.py list
口径：以 state/ledger/jobs.db 的 runs 为准（唯一真源），复盘记录写 state/work/fail-rca.jsonl。
判重键 = 任务名 + 错误特征前 60 字；有记录即视为已复盘（不论状态）。
"""
import argparse, json, os, sqlite3, shutil, sys, tempfile, time, datetime, re

W = "/home/j/.openclaw/workspace"
DB = os.path.join(W, "state/ledger/jobs.db")
REC = os.path.join(W, "state/work/fail-rca.jsonl")

BENIGN = ("skipped", "paused", "owner is unavailable", "restart", "已被新会话取代",
          "superseded", "quiet", "quiet-window", "环境中断")

def db():
    t = tempfile.mktemp(suffix=".db")
    shutil.copy(DB, t)
    c = sqlite3.connect(t)
    c.row_factory = sqlite3.Row
    return c

def norm(err, status=""):
    s = (err or "").strip()
    if not s:
        return "<无错误文本 status=%s>" % (status or "?")
    s = re.sub(r"\b\d{4}-\d{2}-\d{2}T[\d:.+-]+", "<ts>", s)
    s = re.sub(r"\bid[=:]\s*[\w-]{8,}", "id=<x>", s)
    s = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "<t>", s)
    return s[:60]

def load_recs():
    out = []
    if os.path.exists(REC):
        for line in open(REC, encoding="utf-8"):
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except Exception: pass
    return out

def failures(hours):
    c = db()
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - hours * 3600))
    q = """select name, agent, started, status, coalesce(error,'') as error from runs
           where status not in ('ok','skipped') and started >= ? order by started desc"""
    rows = [dict(r) for r in c.execute(q, (since,))]
    # 2026-11-24: 在飞任务(仍 running 且启动不足 30 分钟)不算失败，避免把正在跑的 cron 记成孤儿
    cutoff = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 30*60))
    rows = [r for r in rows if not (r.get("status")=="running" and (r.get("started") or "") > cutoff)]
    return rows

def cmd_check(a):
    recs = load_recs()
    keys = {(r.get("job"), r.get("sig")) for r in recs}
    groups = {}
    for r in failures(a.hours):
        err = r["error"] or ""
        if any(b in err.lower() for b in BENIGN):
            continue
        if r["status"] == "running":
            k = (r["name"], "<孤儿记录: 起了没收回，进程被中断>")
        else:
            k = (r["name"], norm(err, r["status"]))
        g = groups.setdefault(k, {"job": r["name"], "sig": ("<孤儿记录: 起了没收回，进程被中断>" if r["status"]=="running" else norm(err, r["status"])), "n": 0, "first": r["started"],
                                  "last": r["started"], "sample": err[:200]})
        g["n"] += 1
        if r["started"] < g["first"]: g["first"] = r["started"]
        if r["started"] > g["last"]: g["last"] = r["started"]
    todo = [g for k, g in groups.items() if k not in keys]
    covered = len(groups) - len(todo)
    if not todo:
        print("✅ R34 近 %dh 失败 %d 类，全部已复盘（覆盖 %d）" % (a.hours, len(groups), covered))
        return 0
    print("❌ R34 近 %dh 有 %d 类失败未复盘（已复盘 %d 类）：" % (a.hours, len(todo), covered))
    for g in sorted(todo, key=lambda x: -x["n"]):
        print("  · %s ×%d  [%s → %s]" % (g["job"], g["n"], g["first"][5:16], g["last"][5:16]))
        print("    特征: %s" % g["sig"])
    print("\n补记录：python3 tools/fail-rca.py add '<任务名>' --sig '<特征>' --cause '<根因>' --fix '<修法>' --status fixed|monitoring|blocked")
    return 1

def cmd_add(a):
    rec = {"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "job": a.job,
           "sig": norm(a.sig), "cause": a.cause, "fix": a.fix, "status": a.status,
           "by": os.environ.get("USER", "main")}
    with open(REC, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("已记录复盘：%s ｜ %s" % (rec["job"], rec["status"]))
    return 0

def cmd_close_orphans(a):
    """把 started 超过 --hours 仍 status=running 的记录标成 orphaned（进程被中断，永远收不了尾）。"""
    c = db()
    cutoff = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - a.hours * 3600))
    rows = [dict(r) for r in c.execute(
        "select receipt_id, name, started from runs where status='running' and started < ?", (cutoff,))]
    if not rows:
        print("没有超过 %dh 的孤儿记录" % a.hours)
        return 0
    # 写回真实库（本工具是 jobs.db 的合法入口之一）
    real = sqlite3.connect(DB)
    n = 0
    for r in rows:
        real.execute("update runs set status='orphaned', error=coalesce(nullif(error,''),'未收尾：进程被中断，无结束记录') where receipt_id=?",
                     (r["receipt_id"],))
        n += 1
    real.commit(); real.close()
    print("已标记 %d 条孤儿记录为 orphaned：%s" % (n, ", ".join(sorted({r["name"] for r in rows}))[:200]))
    return 0


def cmd_list(a):
    for r in load_recs():
        print("%s  %-28s %-10s %s" % (r["ts"], r["job"][:28], r["status"], r["cause"][:50]))
    return 0

ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd")
p1 = sub.add_parser("check"); p1.add_argument("--hours", type=int, default=48)
p2 = sub.add_parser("add"); p2.add_argument("job"); p2.add_argument("--sig", required=True)
p2.add_argument("--cause", required=True); p2.add_argument("--fix", required=True)
p2.add_argument("--status", default="fixed", choices=["fixed", "monitoring", "blocked"])
p4 = sub.add_parser("close-orphans"); p4.add_argument("--hours", type=int, default=2)
p3 = sub.add_parser("list")
a = ap.parse_args()
sys.exit({"check": cmd_check, "add": cmd_add, "list": cmd_list, "close-orphans": cmd_close_orphans}.get(a.cmd or "check", cmd_check)(a))
