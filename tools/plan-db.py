#!/usr/bin/env python3
"""plan-db.py —— 计划/记分归一：把 scores.jsonl、adjustments-*.json 导入 state/plan/plan.db（幂等）

表: scores(date,no,title,status,points,reason) / adjustments(date,why,delta)
"""
import os, sys, json, sqlite3, hashlib

W = '/home/j/.openclaw/workspace'
DB = os.path.join(W, 'state/plan/plan.db')
P = os.path.join(W, 'state/plan')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS scores(date TEXT, no TEXT, title TEXT, status TEXT, points INT,
  reason TEXT, src TEXT, hash TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS adjustments(date TEXT, why TEXT, delta INT, src TEXT, hash TEXT UNIQUE);
'''

def h(s): return hashlib.sha1(s.encode('utf-8', 'replace')).hexdigest()

def main():
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    ins = 0
    f = os.path.join(P, 'scores.jsonl')
    if os.path.exists(f):
        for line in open(f, encoding='utf-8', errors='replace'):
            line = line.strip()
            if not line: continue
            try: o = json.loads(line)
            except Exception: continue
            try:
                c.execute('INSERT INTO scores VALUES(?,?,?,?,?,?,?,?)',
                          (o.get('date'), str(o.get('no') or ''), o.get('title'), o.get('status'),
                           int(o.get('points') or 0), o.get('reason'), 'scores.jsonl', h(line)))
                ins += 1
            except sqlite3.IntegrityError: pass
    for name in sorted(os.listdir(P)):
        if not (name.startswith('adjustments-') and name.endswith('.json')): continue
        day = name[len('adjustments-'):-5]
        try: arr = json.load(open(os.path.join(P, name), encoding='utf-8'))
        except Exception: continue
        for a in arr if isinstance(arr, list) else []:
            key = name + '|' + json.dumps(a, ensure_ascii=False, sort_keys=True)
            try:
                c.execute('INSERT INTO adjustments VALUES(?,?,?,?,?)',
                          (day, a.get('why'), int(a.get('delta') or 0), name, h(key)))
                ins += 1
            except sqlite3.IntegrityError: pass
    c.commit()
    s = c.execute('select count(*), coalesce(sum(points),0) from scores').fetchone()
    a = c.execute('select count(*), coalesce(sum(delta),0) from adjustments').fetchone()
    print('plan.db: scores %d 行/计分和 %s；adjustments %d 行/调整和 %s；本次新增 %d' % (s[0], s[1], a[0], a[1], ins))
    return 0

if __name__ == '__main__':
    sys.exit(main())
