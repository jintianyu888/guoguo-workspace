#!/usr/bin/env python3
"""ops-ledger.py — 运维账本总览（备份 / 升级 / 执行 三本一屏）2026-11-21

统一口径：
  备份 → state/ledger/backups.db  (archives/copies/runs/retention)
  升级 → state/ledger/upgrades.db (events/runs)
  执行 → state/ledger/exec.db     (每条执行任务)
用法: ops-ledger.py [backup|upgrade|exec|all] [n]
"""
import os, sqlite3, sys

L = "/home/j/.openclaw/workspace/state/ledger"


def q(db, sql, args=()):
    p = os.path.join(L, db)
    if not os.path.exists(p):
        return None
    c = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.Error:
        return None
    finally:
        c.close()


def backup(n):
    print("── 备份账本 backups.db ──")
    for k, sql in (("归档", "SELECT count(*) FROM archives"),
                   ("副本", "SELECT count(*) FROM copies"),
                   ("运行", "SELECT count(*) FROM runs")):
        r = q("backups.db", sql)
        print("  %s：%s" % (k, r[0][0] if r else "表缺失"))
    for r in q("backups.db", "SELECT at,action,file,bytes,IFNULL(approved_by,'') FROM retention ORDER BY id DESC LIMIT ?", (n,)) or []:
        gb = ("%.0fG" % (r[3] / 1073741824)) if r[3] else ""
        print("  %s %-5s %s %s %s" % (r[0], r[1], (r[2] or "")[:40], gb, r[4]))


def upgrade(n):
    print("── 升级账本 upgrades.db ──")
    rows = q("upgrades.db", "SELECT ts,stage,IFNULL(from_version,''),IFNULL(to_version,''),IFNULL(msg,'') "
                            "FROM events ORDER BY id DESC LIMIT ?", (n,))
    if rows is None:
        print("  ❌ 库不存在")
        return
    for r in rows:
        print("  %s %-9s %s%s %s" % (r[0], r[1], (r[2] + "→") if r[2] else "", r[3], (r[4] or "")[:50]))


def jobs(n):
    print("── 定时任务账本 jobs.db ──")
    r = q("jobs.db", "SELECT count(*) FROM jobs WHERE enabled=1")
    tot = q("jobs.db", "SELECT count(*) FROM runs")
    if r is None:
        print("  ❌ 库不存在（跑 tools/job-ledger.py sync）")
        return
    print("  启用任务 %s，运行记录累计 %s" % (r[0][0], tot[0][0] if tot else 0))
    for x in q("jobs.db", "SELECT name,status,started,seconds FROM runs ORDER BY started DESC LIMIT ?", (n,)) or []:
        print("  %s %-3s %-30s %ss" % (x[2], x[1], (x[0] or "")[:30], x[3]))


def exe(n):
    print("── 执行账本 exec.db ──")
    rows = q("exec.db", "SELECT finished,task,done FROM tasks ORDER BY id DESC LIMIT ?", (n,))
    if not rows:
        print("  （无记录或表名不同）")
        return
    for r in rows:
        print("  %s %-4s %s" % (r[0], r[2], (r[1] or "")[:60]))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    if what in ("backup", "all"):
        backup(n)
    if what in ("upgrade", "all"):
        upgrade(n)
    if what in ("jobs", "all"):
        jobs(n)
    if what in ("exec", "all"):
        exe(n)
