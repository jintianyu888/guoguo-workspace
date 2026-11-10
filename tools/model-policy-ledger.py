#!/usr/bin/env python3
"""model-policy-ledger.py —— 模型使用侧策略唯一账（2026-11-01 立）
记录每次模型使用策略变更：谁、何时、哪个 agent、把什么改成什么、为什么、怎么审的。
与 ledger_events 同库（ledger.db），独立表 + 链式哈希。
用法:
  model-policy-ledger.py --agent <名> --field <primary|fallbacks|utility> \
      --from <旧值> --to <新值> --reason <原因> --reviewer <审核情况> [--writer <人>]
"""
import sqlite3, os, sys, json, hashlib, datetime, argparse

W = '/home/j/.openclaw/workspace'
DB = W + '/state/ledger/ledger.db'

def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')

def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def schema(c):
    c.execute('''create table if not exists model_policy(
        id integer primary key autoincrement,
        ts text not null,
        writer text not null,
        agent text not null,
        field text not null,
        from_value text,
        to_value text,
        reason text,
        reviewer text,
        content_sha256 text not null,
        trace_id text not null,
        prev_hash text)''')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--agent', required=True)
    ap.add_argument('--field', required=True)
    ap.add_argument('--from', dest='frm', default='')
    ap.add_argument('--to', dest='to', default='')
    ap.add_argument('--reason', default='')
    ap.add_argument('--reviewer', default='')
    ap.add_argument('--writer', default='main')
    a = ap.parse_args()
    c = sqlite3.connect(DB, timeout=5)
    c.execute('pragma journal_mode=WAL')
    c.execute('pragma busy_timeout=5000')
    schema(c)
    ts = now()
    body = json.dumps({'ts':ts,'writer':a.writer,'agent':a.agent,'field':a.field,
                       'from':a.frm,'to':a.to,'reason':a.reason,'reviewer':a.reviewer},
                      ensure_ascii=False, sort_keys=True)
    h = sha(body)
    prev = c.execute('select content_sha256 from model_policy order by id desc limit 1').fetchone()
    prev = prev[0] if prev else None
    c.execute('''insert into model_policy(ts,writer,agent,field,from_value,to_value,reason,reviewer,content_sha256,trace_id,prev_hash)
                 values(?,?,?,?,?,?,?,?,?,?,?)''',
              (ts, a.writer, a.agent, a.field, a.frm, a.to, a.reason, a.reviewer, h, h[:16], prev))
    c.commit()
    print('OK 记录 agent=%s field=%s %s->%s trace=%s' % (a.agent, a.field, a.frm, a.to, h[:16]))
    return 0

if __name__ == '__main__':
    sys.exit(main())
