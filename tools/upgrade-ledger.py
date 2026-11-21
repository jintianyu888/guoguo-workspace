#!/usr/bin/env python3
"""upgrade-ledger.py — 升级账本（唯一真源 state/ledger/upgrades.db）

与备份账本 backups.db 同构：
  runs(id,kind,started,finished,seconds,result,note)
  events(id,ts,stage,from_version,to_version,rc,msg,evidence,rollback)
用法：
  upgrade-ledger.py log <stage> "<msg>" [--from V] [--to V] [--rc N] [--evidence S] [--rollback S]
  upgrade-ledger.py run-start "<kind>"
  upgrade-ledger.py run-end <id> <result> [note]
  upgrade-ledger.py import-jsonl [path]     # 导入旧 state/work/upgrade-ledger.jsonl
  upgrade-ledger.py report [n]
"""
import argparse, json, os, sqlite3, sys, time

DB = "/home/j/.openclaw/workspace/state/ledger/upgrades.db"
OLD = "/home/j/.openclaw/workspace/state/work/upgrade-ledger.jsonl"
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY, kind TEXT, started TEXT, finished TEXT,
  seconds INTEGER, result TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY, ts TEXT, stage TEXT, from_version TEXT, to_version TEXT,
  rc INTEGER, msg TEXT, evidence TEXT, rollback TEXT);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    return c


def log(a):
    c = conn()
    c.execute("INSERT INTO events(ts,stage,from_version,to_version,rc,msg,evidence,rollback) VALUES(?,?,?,?,?,?,?,?)",
              (time.strftime("%F %T"), a.stage, a.__dict__.get("from_version"), a.__dict__.get("to_version"),
               a.rc, a.msg, a.evidence, a.rollback))
    c.commit()
    print("✅ 升级账本 +1：%s %s" % (a.stage, a.msg))


def import_jsonl(path):
    n = 0
    c = conn()
    for line in open(path, errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts = d.get("ts", "")
        if len(ts) == 15:  # 20261105-194947
            ts = "%s-%s-%s %s:%s:%s" % (ts[0:4], ts[4:6], ts[6:8], ts[9:11], ts[11:13], ts[13:15])
        c.execute("INSERT INTO events(ts,stage,msg) VALUES(?,?,?)", (ts, d.get("stage", "?"), d.get("msg", "")))
        n += 1
    c.commit()
    print("导入 %d 条" % n)


def report(n):
    c = conn()
    rows = c.execute("SELECT ts,stage,IFNULL(from_version,''),IFNULL(to_version,''),IFNULL(rc,''),msg "
                     "FROM events ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    print("── 升级账本（最近 %d 条）──" % n)
    for r in rows:
        print("  %s  %-10s %s%s %s" % (r[0], r[1], (r[2] + "→") if r[2] else "", r[3], (r[5] or "")[:70]))
    runs = c.execute("SELECT id,kind,started,finished,result FROM runs ORDER BY id DESC LIMIT 5").fetchall()
    for r in runs:
        print("  [run %s] %s %s→%s %s" % r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("log"); p1.add_argument("stage"); p1.add_argument("msg")
    p1.add_argument("--from", dest="from_version"); p1.add_argument("--to", dest="to_version")
    p1.add_argument("--rc", type=int); p1.add_argument("--evidence"); p1.add_argument("--rollback")
    p2 = sub.add_parser("import-jsonl"); p2.add_argument("path", nargs="?", default=OLD)
    p3 = sub.add_parser("report"); p3.add_argument("n", nargs="?", type=int, default=15)
    a = ap.parse_args()
    if a.cmd == "log":
        log(a)
    elif a.cmd == "import-jsonl":
        import_jsonl(a.path)
    else:
        report(a.n)
