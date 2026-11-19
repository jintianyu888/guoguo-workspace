#!/usr/bin/env python3
"""ledger-migrate.py —— 唯一台账迁移器（2026-11-01 立）
把散落的 JSONL 台账迁入 state/ledger/ledger.db 的 ledger_events 表。
链式哈希 + 迁移水位 + 幂等（source+orig_line 唯一）。
用法:
  ledger-migrate.py --source <jsonl> --name <来源名> [--dry-run]
"""
import sqlite3, os, sys, json, hashlib, datetime, argparse

W = '/home/j/.openclaw/workspace'
DB = W + '/state/ledger/ledger.db'

def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')

def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def schema(c):
    c.execute('''create table if not exists ledger_events(
        id integer primary key autoincrement,
        ts text not null,
        writer text not null,
        action text not null,
        subject text,
        source text not null,
        detail text,
        content_sha256 text not null,
        trace_id text not null,
        prev_hash text,
        migrated_at text,
        orig_line integer,
        unique(source, orig_line))''')
    c.execute('''create table if not exists ledger_migrations(
        source text primary key,
        migrated_lines integer,
        last_line integer,
        migrated_at text,
        verified integer)''')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--action', default='record')
    ap.add_argument('--writer', default='ledger-migrate')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if not os.path.exists(a.source):
        print('ERR 源不存在', a.source); return 2
    lines = open(a.source, encoding='utf-8', errors='replace').read().splitlines()
    c = sqlite3.connect(DB, timeout=5)
    c.execute('pragma journal_mode=WAL')
    c.execute('pragma busy_timeout=5000')
    schema(c)
    # 取已有水位
    row = c.execute('select last_line, migrated_lines from ledger_migrations where source=?', (a.name,)).fetchone()
    start = (row[0] + 1) if row else 1
    done_before = row[1] if row else 0
    prev_hash = None
    # 取本 source 最后一条的 content_sha256 作为链头
    last = c.execute('select content_sha256 from ledger_events where source=? order by orig_line desc limit 1', (a.name,)).fetchone()
    prev_hash = last[0] if last else None
    inserted = 0
    if a.dry_run:
        print('DRY-RUN source=%s 总行数=%d 已迁=%d 待迁=%d' % (a.name, len(lines), done_before, max(0, len(lines)-done_before)))
        return 0
    for i, ln in enumerate(lines, start=1):
        if i <= done_before:
            continue
        ln = ln.strip()
        if not ln:
            continue
        # 尽力解析原记录，提取 ts/writer/action；失败则整行作 detail
        ts = now(); writer = a.writer; action = a.action; subject = None; detail = ln
        try:
            obj = json.loads(ln)
            detail = ln
            ts = obj.get('ts') or obj.get('time') or now()
            writer = obj.get('writer') or obj.get('operator') or obj.get('agent') or a.writer
            action = obj.get('action') or obj.get('key') or obj.get('type') or a.action
            subject = str(obj.get('subject') or obj.get('title') or obj.get('target') or obj.get('file') or obj.get('archive') or '')[:200]
        except Exception:
            pass
        content_hash = sha(ln)
        rec = (ts, writer, action, subject, a.name, detail, content_hash, content_hash[:16], prev_hash, now(), i)
        c.execute('''insert into ledger_events(ts,writer,action,subject,source,detail,content_sha256,trace_id,prev_hash,migrated_at,orig_line)
                     values(?,?,?,?,?,?,?,?,?,?,?)''', rec)
        prev_hash = content_hash
        inserted += 1
    # 水位
    c.execute('''insert into ledger_migrations(source,migrated_lines,last_line,migrated_at,verified)
                 values(?,?,?,?,0)
                 on conflict(source) do update set
                   migrated_lines=migrated_lines+excluded.migrated_lines,
                   last_line=excluded.last_line,
                   migrated_at=excluded.migrated_at''',
              (a.name, inserted, len(lines), now()))
    c.commit()
    # 校验链
    cnt = c.execute('select count(*) from ledger_events where source=?', (a.name,)).fetchone()[0]
    print('OK 迁移 source=%s 新增=%d 累计=%d 水位=%d' % (a.name, inserted, cnt, len(lines)))
    return 0

if __name__ == '__main__':
    sys.exit(main())
