#!/usr/bin/env python3
# exec-ledger.py v1.0 — 统一执行账本（2026-11-15 主公令）
# 每条执行任务记录：完成时间 / 是否完成 / 是否复用经验或技能 / 是否做了优化 / 证据 / 回滚
import argparse, os, sqlite3, sys, datetime, json
W = '/home/j/.openclaw/workspace'
DB = os.path.join(W, 'state/ledger/exec.db')

def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS tasks(
      id INTEGER PRIMARY KEY,
      task TEXT NOT NULL,
      category TEXT,
      started TEXT,
      finished TEXT,
      done TEXT,
      reused TEXT,
      optimized TEXT,
      evidence TEXT,
      rollback TEXT,
      task_id INTEGER
    );''')
    c.execute("CREATE TABLE IF NOT EXISTS retention(id INTEGER PRIMARY KEY, ts TEXT, mode TEXT, target TEXT, plan_gb INTEGER, detail TEXT)")
    try:
        c.execute("CREATE TRIGGER IF NOT EXISTS retention_no_update BEFORE UPDATE ON retention BEGIN SELECT RAISE(ABORT, 'append-only'); END")
        c.execute("CREATE TRIGGER IF NOT EXISTS retention_no_delete BEFORE DELETE ON retention BEGIN SELECT RAISE(ABORT, 'append-only'); END")
    except Exception:
        pass
    return c

def add(a):
    c = db(); now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur = c.execute('INSERT INTO tasks(task,category,started,finished,done,reused,optimized,evidence,rollback,task_id) VALUES(?,?,?,?,?,?,?,?,?,?)',
      (a.task, a.category or 'ops', a.started or now, now, a.done, a.reused or 'none', a.optimized or 'none', a.evidence or '', a.rollback or '', a.task_id))
    c.commit(); print('#%d 已入账 %s' % (cur.lastrowid, a.task))

def rows(c, n):
    return c.execute('SELECT id,finished,done,task,category,reused,optimized FROM tasks ORDER BY id DESC LIMIT ?', (n,)).fetchall()

def listing(a):
    c = db()
    print('ID   完成时间           结果   类别      复用/优化        任务')
    for r in rows(c, a.n):
        print('%-4d %-19s %-6s %-9s %-16s %s' % (r[0], r[1], r[2], (r[3] or '')[:4] and r[4], (('R:'+r[5])[:8] if r[5] not in ('none','') else '') + (' O:' + r[6][:6] if r[6] not in ('none','') else ''), r[3]))
    t = c.execute('SELECT COUNT(*), SUM(done="ok"), SUM(done!="ok"), SUM(reused NOT IN ("none","")), SUM(optimized NOT IN ("none","")) FROM tasks').fetchone()
    n = t[0] or 1
    print('\n合计 %d 条：完成 %d (%.0f%%)，未完成/失败 %d，复用经验/技能 %d (%.0f%%)，做了优化 %d (%.0f%%)' %
          (t[0], t[1] or 0, 100.0*(t[1] or 0)/n, t[2] or 0, t[3] or 0, 100.0*(t[3] or 0)/n, t[4] or 0, 100.0*(t[4] or 0)/n))

def report(a):
    c = db()
    out = os.path.join(W, 'docs/执行账本-%s.md' % datetime.datetime.now().strftime('%Y-%m'))
    lines = ['# 执行账本 ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), '', '> 真源 state/ledger/exec.db（tools/exec-ledger.py），禁止手改', '', '## 最近 40 条', '']
    for r in rows(c, 40):
        lines.append('- [%s] #%d %s —— %s｜复用=%s｜优化=%s' % (r[1], r[0], r[3], r[2], r[5], r[6]))
    t = c.execute('SELECT COUNT(*), SUM(done="ok"), SUM(reused NOT IN ("none","")), SUM(optimized NOT IN ("none","")) FROM tasks').fetchone()
    n = t[0] or 1
    lines += ['', '## 统计', '', '- 总条数 %d，完成 %d（%.0f%%）' % (t[0], t[1] or 0, 100.0*(t[1] or 0)/n), '- 复用既有经验/技能 %d（%.0f%%）' % (t[2] or 0, 100.0*(t[2] or 0)/n), '- 做了流程/脚本优化 %d（%.0f%%）' % (t[3] or 0, 100.0*(t[3] or 0)/n)]
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('已渲染', out)

def retention_import(a):
    import json
    c = db(); src = os.path.join(W, "state/work/retention-audit.jsonl"); n = 0
    if not os.path.exists(src):
        print("无审计文件"); return
    have = {r[0] for r in c.execute("SELECT ts FROM retention")}
    for line in open(src, encoding="utf-8"):
        line = line.strip()
        if not line: continue
        try: e = json.loads(line)
        except Exception: continue
        if e.get("ts") in have: continue
        c.execute("INSERT INTO retention(ts,mode,target,plan_gb,detail) VALUES(?,?,?,?,?)", (e.get("ts"), e.get("mode"), e.get("target"), e.get("plan_gb"), line[:200]))
        n += 1
    c.commit(); print("导入托管审计", n, "条")

p = argparse.ArgumentParser()
s = p.add_subparsers(dest='cmd', required=True)
a1 = s.add_parser('add'); a1.add_argument('task'); a1.add_argument('--category'); a1.add_argument('--done', default='ok'); a1.add_argument('--reused', default='none'); a1.add_argument('--optimized', default='none'); a1.add_argument('--evidence'); a1.add_argument('--rollback'); a1.add_argument('--started'); a1.add_argument('--task-id', type=int); a1.set_defaults(fn=add)
a2 = s.add_parser('list'); a2.add_argument('-n', type=int, default=20); a2.set_defaults(fn=listing)
a3 = s.add_parser('report'); a3.set_defaults(fn=report)
a5 = s.add_parser('retention-import'); a5.set_defaults(fn=retention_import)
a = p.parse_args(); a.fn(a)