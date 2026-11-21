#!/usr/bin/env python3
"""retention-ledger.py — 保留/删除动作入 backups.db（2026-11-21 统一账本）

之前 retention-audit.jsonl、retention-deleted.jsonl 是游离的，查不到「哪天删了什么」。
现在统一进 state/ledger/backups.db 的 retention 表，和 archives/copies/runs 同库。
用法：
  retention-ledger.py import        # 把两个 jsonl 全量导入（幂等）
  retention-ledger.py add --action delete --file X --bytes N --note "..." [--approved 金鱼]
  retention-ledger.py report [n]
"""
import argparse, json, os, sqlite3, time

DB = "/home/j/.openclaw/workspace/state/ledger/backups.db"
W = "/home/j/.openclaw/workspace/state/work"
SRC = [(os.path.join(W, "retention-audit.jsonl"), "audit"),
       (os.path.join(W, "retention-deleted.jsonl"), "delete")]


def conn():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS retention(
      id INTEGER PRIMARY KEY, at TEXT, action TEXT, file TEXT, bytes INTEGER,
      note TEXT, approved_by TEXT, src TEXT, UNIQUE(at,action,file));
    """)
    return c


def do_import():
    c = conn(); n = 0
    for path, kind in SRC:
        if not os.path.exists(path):
            continue
        for line in open(path, errors="ignore"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            at = d.get("at") or ""
            if kind == "audit":
                act = "plan" if d.get("mode") == "dryrun" else "apply"
                f, by, note = d.get("target", ""), None, "plan_gb=%s" % d.get("plan_gb")
                b = None
            else:
                act, f, by = "delete", d.get("file", ""), d.get("approved_by")
                b, note = d.get("bytes"), d.get("reason")
            cur = c.execute("INSERT OR IGNORE INTO retention(at,action,file,bytes,note,approved_by,src) "
                            "VALUES(?,?,?,?,?,?,?)", (at, act, f, b, note, by, kind))
            n += cur.rowcount
    c.commit()
    print("导入 %d 条（去重后新增）" % n)


def add(a):
    c = conn()
    c.execute("INSERT OR IGNORE INTO retention(at,action,file,bytes,note,approved_by,src) VALUES(?,?,?,?,?,?,?)",
              (time.strftime("%F %T"), a.action, a.file, a.bytes, a.note, a.approved, "manual"))
    c.commit()
    print("✅ retention +1")


def report(n):
    c = conn()
    for r in c.execute("SELECT at,action,file,bytes,IFNULL(approved_by,''),IFNULL(note,'') "
                       "FROM retention ORDER BY id DESC LIMIT ?", (n,)):
        gb = ("%.0fG" % (r[3] / 1073741824)) if r[3] else ""
        print("  %s  %-6s %s %s %s" % (r[0], r[1], (r[2] or "")[:52], gb, r[5][:40]))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("import")
    aa = s.add_parser("add"); aa.add_argument("--action", required=True); aa.add_argument("--file", required=True)
    aa.add_argument("--bytes", type=int); aa.add_argument("--note"); aa.add_argument("--approved")
    rr = s.add_parser("report"); rr.add_argument("n", nargs="?", type=int, default=12)
    a = p.parse_args()
    if a.cmd == "import":
        do_import()
    elif a.cmd == "add":
        add(a)
    else:
        report(a.n)
