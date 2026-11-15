#!/usr/bin/env python3
# backup-ledger.py v1.0 — 备份唯一账本（2026-11-15 主公令：每天备份时间/数量必须记账，失败件及时清）
# 库: state/ledger/backups.db  用法见 --help
import argparse, os, re, sqlite3, sys, datetime, hashlib, subprocess

W = "/home/j/.openclaw/workspace"
DB = os.path.join(W, "state/ledger/backups.db")
DISKS = {
    "X": "/mnt/x/openclaw-backups",
    "D": "/mnt/d/openclaw-backups",
    "E": "/mnt/e/openclaw-backups",
    "H": "/mnt/h/openclaw-backups",
    "NAS": "/mnt/nas/archive/jinyu/openclaw-archives",
}
NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})")

def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS archives(id INTEGER PRIMARY KEY, name TEXT UNIQUE, day TEXT, size INTEGER, created TEXT, duplicate_of TEXT);
    CREATE TABLE IF NOT EXISTS copies(id INTEGER PRIMARY KEY, name TEXT, disk TEXT, path TEXT, size INTEGER, mtime TEXT, has_sha INTEGER DEFAULT 0, UNIQUE(name,disk));
    CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, kind TEXT, started TEXT, finished TEXT, seconds INTEGER, result TEXT, produced INTEGER, note TEXT);
    CREATE TABLE IF NOT EXISTS parts(id INTEGER PRIMARY KEY, path TEXT UNIQUE, disk TEXT, size INTEGER, mtime TEXT);
    """)
    return c

def parse(name):
    m = NAME_RE.search(name)
    if not m:
        return None
    d = "%sT%s:%s:%s" % m.groups()
    return m.group(1), d

def scan(args):
    c = db()
    now = datetime.datetime.now()
    seen = 0
    for disk, root in DISKS.items():
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            path = os.path.join(root, fn)
            if not os.path.isfile(path):
                continue
            st = os.stat(path)
            mt = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            if fn.endswith(".tar.gz.part"):
                c.execute("INSERT OR REPLACE INTO parts(path,disk,size,mtime) VALUES(?,?,?,?)", (path, disk, st.st_size, mt))
            elif fn.endswith(".tar.gz"):
                p = parse(fn)
                if not p:
                    continue
                day, created = p
                c.execute("INSERT OR IGNORE INTO archives(name,day,size,created) VALUES(?,?,?,?)", (fn, day, st.st_size, created))
                c.execute("INSERT OR REPLACE INTO copies(name,disk,path,size,mtime,has_sha) VALUES(?,?,?,?,?,0)", (fn, disk, path, st.st_size, mt))
                seen += 1
            elif fn.endswith(".sha256"):
                continue
    for (pp,) in c.execute("SELECT path FROM parts").fetchall():
        if not os.path.exists(pp):
            c.execute("DELETE FROM parts WHERE path=?", (pp,))
    for (pp,) in c.execute("SELECT path FROM copies").fetchall():
        if not os.path.exists(pp):
            c.execute("DELETE FROM copies WHERE path=?", (pp,))
    c.execute("DELETE FROM archives WHERE name NOT IN (SELECT name FROM copies)")
    c.commit()
    print("扫描副本 %d 条" % seen)
    report(c)

def report(c=None, days=21):
    c = c or db()
    rows = c.execute("SELECT day, name, size FROM archives ORDER BY day, name").fetchall()
    if not rows:
        print("账本为空，先跑 scan")
        return
    days_sorted = sorted({r[0] for r in rows})[-days:]
    print("日期        份数  大小      盘位            生成时间   状态")
    for d in days_sorted:
        names = [r for r in rows if r[0] == d]
        total = sum(r[2] for r in names) / (1024 ** 3)
        for n, sz, created in [(r[1], r[2], "") for r in names]:
            disks = [x[0] for x in c.execute("SELECT disk FROM copies WHERE name=? ORDER BY disk", (n,))]
            cr = c.execute("SELECT created FROM archives WHERE name=?", (n,)).fetchone()[0]
            st = "OK" if len(disks) >= 2 else "仅1份(!)"
            print("%s  %-3d  %6.1fG  %-14s  %s  %s" % (d, len(names), sz / (1024 ** 3), ",".join(disks) or "-", cr[11:], st))
        if len(names) > 1:
            print("   ⚠ %s 有 %d 份（应 1 份/天）" % (d, len(names)))
    parts = c.execute("SELECT disk, size, path, mtime FROM parts ORDER BY mtime DESC").fetchall()
    if parts:
        print("\n残片 .part：")
        for disk, sz, p, mt in parts:
            print("  %-3s %6.1fG  %s  (%s)" % (disk, sz / (1024 ** 3), os.path.basename(p)[:52], mt))

def run_start(args):
    c = db()
    t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = c.execute("INSERT INTO runs(kind,started,result) VALUES(?,?,?)", (args.kind, t, "running"))
    c.commit()
    print(cur.lastrowid)

def run_end(args):
    c = db()
    t = datetime.datetime.now()
    row = c.execute("SELECT started FROM runs WHERE id=?", (args.id,)).fetchone()
    if not row:
        sys.exit("run id 不存在")
    st = datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE runs SET finished=?, seconds=?, result=?, produced=?, note=? WHERE id=?",
              (t.strftime("%Y-%m-%d %H:%M:%S"), int((t - st).total_seconds()), args.result, args.produced, args.note or "", args.id))
    c.commit()
    print("run %s 结束: %s %ss 产出 %s" % (args.id, args.result, int((t - st).total_seconds()), args.produced))

def runs(args):
    c = db()
    for r in c.execute("SELECT id,kind,started,finished,seconds,result,produced,note FROM runs ORDER BY id DESC LIMIT ?", (args.n,)):
        print(" | ".join(str(x) if x is not None else "-" for x in r))
    tot = c.execute("SELECT COUNT(*), SUM(seconds) FROM runs").fetchone()
    ok = c.execute("SELECT COUNT(*) FROM runs WHERE result='ok'").fetchone()[0]
    print("\n累计 %s 次运行，成功 %s，总耗时 %.1f 小时" % (tot[0], ok, (tot[1] or 0) / 3600))

def janitor(args):
    c = db()
    now = datetime.datetime.now()
    killed = []
    for path, disk, size, mt in c.execute("SELECT path,disk,size,mtime FROM parts").fetchall():
        age = (now - datetime.datetime.strptime(mt, "%Y-%m-%d %H:%M")).total_seconds() / 3600
        if age >= args.hours:
            killed.append((disk, size, path, age))
    for disk, size, path, age in killed:
        print("%s清 %-3s %6.1fG 龄 %.1fh  %s" % ("[apply] " if args.apply else "[dry]   ", disk, size / (1024 ** 3), age, os.path.basename(path)))
        if args.apply:
            try:
                os.remove(path)
            except OSError as e:
                print("  删除失败:", e)
    if not killed:
        print("无超过 %.0f 小时的残片" % args.hours)

def count(args):
    c = db()
    if args.day:
        n = c.execute("SELECT COUNT(*) FROM archives WHERE day=?", (args.day,)).fetchone()[0]
    else:
        n = c.execute("SELECT COUNT(*) FROM archives").fetchone()[0]
    print(n)

p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="cmd", required=True)
sub.add_parser("scan").set_defaults(fn=scan)
rp = sub.add_parser("report"); rp.add_argument("--days", type=int, default=21); rp.set_defaults(fn=lambda a: report(None, a.days))
s1 = sub.add_parser("run-start"); s1.add_argument("kind"); s1.set_defaults(fn=run_start)
s2 = sub.add_parser("run-end"); s2.add_argument("id", type=int); s2.add_argument("result"); s2.add_argument("produced", type=int); s2.add_argument("--note"); s2.set_defaults(fn=run_end)
s3 = sub.add_parser("runs"); s3.add_argument("-n", type=int, default=15); s3.set_defaults(fn=runs)
s5 = sub.add_parser("count"); s5.add_argument("--day"); s5.set_defaults(fn=count)
s4 = sub.add_parser("janitor"); s4.add_argument("--hours", type=float, default=6); s4.add_argument("--apply", action="store_true"); s4.set_defaults(fn=janitor)
a = p.parse_args()
a.fn(a)
