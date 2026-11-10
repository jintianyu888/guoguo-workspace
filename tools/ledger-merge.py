#!/usr/bin/env python3
"""ledger-merge.py —— 把散落的 JSONL/JSON 账本归一到单个 SQLite（幂等、可重跑）

用法: ledger-merge.py <target.db> <source>[:source2...]
  每个 source 可以是 .jsonl（逐行）或 .json（整份一条）
  表结构: events(id INTEGER PRIMARY KEY, ts TEXT, source TEXT, kind TEXT, raw TEXT,
                 hash TEXT UNIQUE)  —— hash = sha1(source + 原始行)，重复导入自动跳过
"""
import sys, os, json, sqlite3, hashlib, time

SCHEMA = '''CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, source TEXT, kind TEXT, raw TEXT, hash TEXT UNIQUE)'''

def ts_of(o, fallback):
    for k in ('ts','time','timestamp','at','date','datetime','when'):
        v = o.get(k) if isinstance(o, dict) else None
        if v: return str(v)[:32]
    return fallback

def kind_of(o):
    if not isinstance(o, dict): return ''
    for k in ('kind','type','event','action','status','result','step'):
        if o.get(k): return str(o[k])[:40]
    return ''

def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    db = sys.argv[1]
    os.makedirs(os.path.dirname(db), exist_ok=True)
    c = sqlite3.connect(db)
    c.executescript(SCHEMA)
    ins = 0; dup = 0; bad = 0
    for src in sys.argv[2].split(':'):
        if not os.path.exists(src):
            print('  跳过（不存在）:', src); continue
        raw_lines = []
        if src.endswith('.jsonl'):
            raw_lines = [l.strip() for l in open(src, encoding='utf-8', errors='replace') if l.strip()]
        else:
            t = open(src, encoding='utf-8', errors='replace').read()
            raw_lines = [t]
        for line in raw_lines:
            try:
                o = json.loads(line)
            except Exception:
                o = line
            h = hashlib.sha1((src + '|' + line).encode('utf-8', 'replace')).hexdigest()
            try:
                c.execute('INSERT INTO events(ts,source,kind,raw,hash) VALUES(?,?,?,?,?)',
                          (ts_of(o, ''), src, kind_of(o), line[:4000], h))
                ins += 1
            except sqlite3.IntegrityError:
                dup += 1
            except Exception:
                bad += 1
    c.commit()
    n = c.execute('select count(*) from events').fetchone()[0]
    print('%s: 新增 %d｜重复跳过 %d｜异常 %d｜总行数 %d' % (db, ins, dup, bad, n))
    return 0

if __name__ == '__main__':
    sys.exit(main())
