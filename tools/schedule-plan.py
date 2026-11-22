#!/usr/bin/env python3
"""schedule-plan.py v1.0 — 用实测耗时排任务时间（2026-11-15 主公令）
真源: openclaw cron list --json 的 state.lastDurationMs + 固定窗口规则
用法:
  schedule-plan.py sync            同步最新任务与实测耗时到 state/ledger/schedule.db
  schedule-plan.py report          输出总表/同分钟碰撞/窗口冲突，写 docs/调度总表-YYYYMMDD.md
  schedule-plan.py gaps           只看需要隔开的长任务与空档
"""
import json, os, re, sqlite3, subprocess, sys, datetime

W = '/home/j/.openclaw/workspace'
DB = os.path.join(W, 'state/ledger/schedule.db')
RED = [(0,10,'备份窗口(01:00起,约3h)'), (255,275,'断网窗/静默 04:00-06:05'), (465,495,'重启红区 07:45-08:15')]
PEAK = [(540,720,'早高峰 09:00-12:00'), (840,1080,'午高峰 14:00-18:00')]

def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, name TEXT, agent TEXT, expr TEXT, enabled INTEGER, timeout_s INTEGER, dur_ms INTEGER, last_run TEXT, last_status TEXT, updated TEXT);")
    return c

def cron():
    r = subprocess.run(['openclaw','cron','list','--json'], capture_output=True, text=True, timeout=600)
    d = json.loads(r.stdout)
    return d if isinstance(d, list) else d.get('jobs', d)

def sync():
    c = db(); n = 0
    for j in cron():
        st = j.get('state') or {}
        ex = (j.get('schedule') or {}).get('expr') or ''
        lr = st.get('lastRunAtMs')
        c.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)", (
            j['id'], j.get('name'), j.get('effectiveAgentId') or j.get('agentId'), ex,
            1 if j.get('enabled') else 0, (j.get('payload') or {}).get('timeoutSeconds'),
            st.get('lastDurationMs'), datetime.datetime.fromtimestamp(lr/1000).strftime('%F %H:%M') if lr else None,
            st.get('lastRunStatus'), datetime.datetime.now().strftime('%F %H:%M')))
        n += 1
    c.commit(); print('同步', n, '条')

def minute(expr):
    m = re.match(r'^(\S+)\s+(\S+)\s', expr or '')
    if not m: return None
    mm, hh = m.group(1), m.group(2)
    if not re.fullmatch(r'\d+', mm) or not re.fullmatch(r'\d+', hh): return None
    return int(hh) * 60 + int(mm)

def report():
    c = db()
    rows = c.execute("SELECT id,name,agent,expr,timeout_s,dur_ms,last_run,last_status FROM jobs WHERE enabled=1 ORDER BY expr").fetchall()
    print('%-28s %-12s %5s %8s %-9s %s' % ('任务','分钟','超时m','实测m','状态','时间表达式'))
    coll = {}
    red = []
    for r in rows:
        jid, name, agent, expr, to, dur, lr, ls = r
        mm = minute(expr)
        dmin = (dur or 0)/60000.0
        print('%-28s %-12s %5s %8.1f %-9s %s' % ((name or '')[:26], mm if mm is not None else expr, (to or 0)//60, dmin, ls or '-', expr))
        if mm is not None and re.fullmatch(r'\d+ \d+ .*', expr or ''):
            coll.setdefault(mm, []).append(name)
        if mm is not None:
            for a, b, lab in RED:
                if a <= mm <= b: red.append((name, mm, lab))
    print()
    bad = {k: v for k, v in coll.items() if len(v) > 1}
    print('== 同分钟碰撞', len(bad), '组')
    for k, v in sorted(bad.items()):
        print('  %02d:%02d  %s' % (k//60, k%60, ' / '.join(x[:18] for x in v)))
    print()
    print('== 落在红线/静默窗', len(red), '条')
    for name, mm, lab in red:
        print('  %02d:%02d  %s  [%s]' % (mm//60, mm%60, name, lab))
    out = os.path.join(W, 'docs', '调度总表-真源.md')
    lines = ['# 调度总表 ' + datetime.datetime.now().strftime('%F %H:%M'), '',
             '> 真源 state/ledger/schedule.db（tools/schedule-plan.py sync），耗时取 cron state.lastDurationMs', '',
             '## 实测耗时', '', '任务 | 分钟 | 超时(m) | 实测(m) | 状态 | expr']
    for r in rows:
        mm = minute(r[3])
        lines.append('%s | %s | %s | %.1f | %s | %s' % (r[1], mm if mm is not None else r[3], (r[4] or 0)//60, (r[5] or 0)/60000.0, r[7] or '-', r[3]))
    lines += ['', '## 同分钟碰撞 %d 组' % len(bad)]
    for k, v in sorted(bad.items()):
        lines.append('- %02d:%02d  %s' % (k//60, k%60, ' / '.join(v)))
    lines += ['', '## 红线/静默窗 %d 条' % len(red)]
    for name, mm, lab in red:
        lines.append('- %02d:%02d  %s  [%s]' % (mm//60, mm%60, name, lab))
    block = '\n'.join(lines) + '\n'
    B = '<!-- AUTO:BEGIN 本段由 tools/schedule-plan.py 生成，勿手改 -->'
    E = '<!-- AUTO:END -->'
    try:
        doc = open(out, encoding='utf-8').read()
    except FileNotFoundError:
        doc = '# 调度总表（唯一真源）\n\n' + B + '\n' + E + '\n'
    if B in doc and E in doc:
        pre, rest = doc.split(B, 1)
        _, post = rest.split(E, 1)
        doc = pre + B + '\n' + block + E + post
    else:
        doc = doc.rstrip() + '\n\n' + B + '\n' + block + E + '\n'
    open(out, 'w', encoding='utf-8').write(doc)
    print()
    print('已写', out)

def gaps():
    c = db()
    rows = c.execute("SELECT name,expr,dur_ms FROM jobs WHERE enabled=1 AND dur_ms>600000 ORDER BY dur_ms DESC").fetchall()
    print('== 长任务(>10分钟)与其后续空档')
    total = 0
    for name, expr, dur in rows:
        mm = minute(expr); d = (dur or 0)/60000.0
        total += d
        print('  %-30s 起 %s  实测 %.0f 分钟 → 占用至 %s' % ((name or '')[:28], expr, d,
              ('%02d:%02d' % (((mm+int(d))//60) % 24, (mm+int(d)) % 60)) if mm is not None else '?'))
    print('  长任务合计 %.0f 分钟' % total)


def overlaps():
    c = db()
    rows = []
    for name, expr, dur, to in c.execute("SELECT name,expr,dur_ms,timeout_s FROM jobs WHERE enabled=1"):
        mm = minute(expr)
        if mm is None: continue
        if not re.fullmatch(r"\d+ \d+ .*", expr or ""): continue
        d = (dur or 0) / 60000.0
        if d <= 0: d = 1.0
        rows.append((mm, mm + d, name or '', d))
    rows.sort()
    print("== 时段重叠（前一个还没跑完，后一个就开始了）")
    n = 0; ex = 0
    for i in range(len(rows)):
        s1, e1, n1, d1 = rows[i]
        for j in range(i + 1, len(rows)):
            s2, e2, n2, d2 = rows[j]
            if s2 >= e1: break
            # EXEMPT：备份/归档/镜像类长任务与同一时段内的任务属设计内重叠
            # （备份期间由 backup-quiet 暂停其余任务，不算冲突）
            BK=("备份","归档","镜像","tier1","tier2")
            if (any(k in n1 for k in BK) and s2 < 7*60) or (any(k in n2 for k in BK) and s1 < 7*60):
                ex += 1
                continue
            n += 1
            print("  %02d:%02d-%02d:%02d %-26s ↔ %02d:%02d %s" % (s1//60, s1%60, int(e1)//60, int(e1)%60, n1[:24], s2//60, s2%60, n2[:24]))
    print("  合计 %d 处重叠（已豁免备份/归档类设计内重叠 %d 处）" % (n, ex))

cmd = sys.argv[1] if len(sys.argv) > 1 else 'report'
if cmd == 'overlaps':
    overlaps()
else:
    {'sync': sync, 'report': report, 'gaps': gaps}[cmd]()
