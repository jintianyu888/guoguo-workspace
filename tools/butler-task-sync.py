#!/usr/bin/env python3
"""butler-task-sync.py —— 把五大管家的自审（PLAN|/DONE|）并进唯一账本 tasks.db

背景：tasks.db 是唯一真源，但管家只写自审 md，不记账，导致"账本统一了、管家没入账"。
本工具把自审里的机器行转成 tasks.db 行（agent=<butler>, kind='butler'），
DONE 行按文本相似度关掉对应 pending，新增的记 done。

用法:
  run [--dry]     扫描并同步（--dry 只打印不写库）
  status          看各管家最近自审与同步条数
幂等: state/butler-sync/index.json 记 hash -> task no
"""
import json, os, re, sys, glob, hashlib, datetime, sqlite3, difflib, shlex

WS = '/home/j/.openclaw/workspace'
DB = os.path.join(WS, 'state/tasks/tasks.db')
IDX = os.path.join(WS, 'state/butler-sync/index.json')
BUTLERS = [('maint', 'maint'), ('backup', 'backup'), ('model', 'model'),
           ('work', 'work'), ('hermess', 'sheet-music')]


def today():
    return datetime.date.today()


def find_review(wsdir, aid, days=2):
    """找最近 days 天内最新的一份自审。"""
    pats = []
    for base in (os.path.join('/home/j/openclaw-workspaces', wsdir, 'state/self-review'),
                 os.path.join(WS, 'state/self-review')):
        for d in range(days):
            dt = today() - datetime.timedelta(days=d)
            for fmt in ('%Y-%m-%d', '%Y%m%d'):
                s = dt.strftime(fmt)
                pats += [os.path.join(base, s + '.md'),
                         os.path.join(base, '%s-%s.md' % (aid, s)),
                         os.path.join(base, '%s-%s.md' % (wsdir, s))]
    for p in pats:
        if os.path.exists(p):
            return p
        for g in glob.glob(p.replace('.md', '*.md')):
            return g
    return None


def parse(txt):
    done, plan = [], []
    for ln in txt.splitlines():
        s = ln.strip().lstrip('-* ').strip()
        for tag, bucket in (('DONE|', done), ('DONE｜', done), ('PLAN|', plan), ('PLAN｜', plan)):
            if s.startswith(tag):
                v = s[len(tag):].strip()
                if v:
                    bucket.append(v)
                break
    return done, plan


def due_of(text):
    """从计划文本里刮时间：明日/明天 HH:MM 或 今日 HH:MM"""
    d = today()
    if re.search(r'明[日天]', text):
        d = d + datetime.timedelta(days=1)
    m = re.search(r'(\d{1,2})[:：](\d{2})', text)
    if m:
        return '%s %02d:%02d' % (d.isoformat(), int(m.group(1)), int(m.group(2)))
    return '%s 09:00' % d.isoformat()


def eta_of(text):
    m = re.search(r'(\d{1,3})\s*分钟', text)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+(\.\d+)?)\s*小时', text)
    if m:
        return int(float(m.group(1)) * 60)
    return None


def norm(t):
    t = re.sub(r'[（）()\s·，,。.:：;；\-—"\'\"]', '', t)
    return t.lower()[:120]


def verify_for(path, snippet):
    return 'grep -qF %s %s' % (shlex.quote(snippet[:40]), shlex.quote(path))


def main():
    args = sys.argv[1:]
    dry = '--dry' in args
    os.makedirs(os.path.dirname(IDX), exist_ok=True)
    idx = {}
    if os.path.exists(IDX):
        try:
            idx = json.load(open(IDX, encoding='utf-8'))
        except Exception:
            idx = {}

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    added_done = added_plan = closed = 0
    report = []

    for aid, wsdir in BUTLERS:
        p = find_review(wsdir, aid)
        if not p:
            report.append('%s: 未找到近两日自审' % aid)
            continue
        txt = open(p, encoding='utf-8', errors='replace').read()
        done, plan = parse(txt)
        report.append('%s: %s → DONE %d / PLAN %d' % (aid, os.path.basename(p), len(done), len(plan)))

        # 1) DONE：先试着关掉同义的 pending，否则新增一条 done
        for item in done:
            key = aid + ':' + norm(item)
            if key in idx:
                continue
            best, score = None, 0.0
            for row in c.execute("select no,title from tasks where agent=? and status in ('pending','in_progress')", (aid,)):
                s = difflib.SequenceMatcher(None, norm(item), norm(row['title'])).ratio()
                if s > score:
                    best, score = row['no'], s
            if best and score >= 0.6:
                if not dry:
                    c.execute("update tasks set status='done', closed_by=?, updated=?, verify=coalesce(verify,'x') where no=?",
                              (aid, datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'), best))
                closed += 1
                idx[key] = best
            else:
                if not dry:
                    cur = c.execute(
                        "insert into tasks (title,status,kind,grp,prio,notes,verify,created,updated,closed_by,who,agent) "
                        "values (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (item, 'done', 'butler', aid, 'P2', '自审 DONE\n来源: %s' % p,
                         verify_for(p, item), datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
                         datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'), aid, aid, aid))
                    idx[key] = cur.lastrowid
                added_done += 1
            idx[key] = idx.get(key) or 0

        # 2) PLAN：作为明日待办入账
        for item in plan:
            key = aid + ':plan:' + norm(item)
            if key in idx:
                continue
            if not dry:
                cur = c.execute(
                    "insert into tasks (title,status,kind,grp,prio,notes,verify,created,updated,who,agent,due_plan,eta_min) "
                    "values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (item, 'pending', 'butler', aid, 'P2', '自审 PLAN\n来源: %s' % p,
                     verify_for(p, item), datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
                     datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'), aid, aid,
                     due_of(item), eta_of(item)))
                idx[key] = cur.lastrowid
            added_plan += 1

    if not dry:
        c.commit()
        tmp = IDX + '.tmp'
        json.dump(idx, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, IDX)
    c.close()

    print('\n'.join(report))
    print('新增 done %d / 新增 plan %d / 关单 %d%s' % (added_done, added_plan, closed, '（dry）' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
