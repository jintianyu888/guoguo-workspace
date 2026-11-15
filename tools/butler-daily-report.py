#!/usr/bin/env python3
# butler-daily-report.py — 五大管家日报（零 token）
# 生成「昨天干了什么 + 今天计划干什么」，默认打印；--send 走 notify.sh 推送主公
import json, os, sys, subprocess, sqlite3, shutil, datetime, re

WS = '/home/j/.openclaw/workspace'
STATE = os.path.join(WS, 'state')
BUTLERS = [
    ('维护',   'maint',       '/home/j/openclaw-workspaces/maint'),
    ('备份',   'backup',      '/home/j/.openclaw/workspace-backup'),
    ('模型',   'model',       '/home/j/.openclaw/workspace-model'),
    ('干活',   'work',        '/home/j/openclaw-workspaces/work'),
    ('Hermess','hermess',     '/home/j/openclaw-workspaces/sheet-music'),
]
AGENT_ALIAS = {'maint':['maint','维护'],'backup':['backup','备份'],'model':['model','模型'],
               'work':['work','干活'],'hermess':['hermess','sheet-music','乐谱','Hermess']}
AGENT_IDS = {'maint':['maint'],'backup':['backup'],'model':['model'],'work':['work'],'hermess':['sheet-music','hermess']}
def jobs_of(jobs, aid):
    ids = AGENT_IDS.get(aid,[aid])
    return [j for j in jobs if (j.get('agentId') or j.get('agent')) in ids]

def today():
    return datetime.date.today()

def load_cron():
    for fn in (os.path.join(STATE,'tmp','cron_list.json'),):
        pass
    try:
        out = subprocess.run(['openclaw','cron','list','--json'], capture_output=True, text=True, timeout=120)
        d = json.loads(out.stdout)
        jobs = d['jobs'] if isinstance(d, dict) else d
        json.dump({'at':datetime.datetime.now().isoformat(timespec='seconds'),'jobs':jobs},
                  open(os.path.join(STATE,'work','cron-cache.json'),'w'))
        return jobs, 'live'
    except Exception as e:
        try:
            c = json.load(open(os.path.join(STATE,'work','cron-cache.json')))
            return c['jobs'], 'cache@'+c.get('at','?')
        except Exception:
            return [], 'unavailable'

def cron_fires_today(expr, d):
    """支持 m h * * * / m h * * dow / */N * * * * 等常见形式；不认识的返回 None"""
    if not expr or expr.startswith('@'):
        return None
    p = expr.split()
    if len(p) != 5: return None
    mi, hh, dom, mon, dow = p
    def match(field, val, lo, hi):
        if field == '*': return True
        for part in field.split(','):
            if part.startswith('*/'):
                try: step=int(part[2:])
                except: return None
                if (val - lo) % step == 0: return True
            elif '-' in part:
                try:
                    a,b = part.split('-')[:2]; a=int(a); b=int(b)
                except: return None
                if a <= val <= b: return True
            else:
                try:
                    if int(part) == val: return True
                except: return None
        return False
    ok = match(mon, d.month, 1, 12)
    if ok is False: return False
    if dow != '*':
        # cron: 0=Sunday
        w = (d.weekday()+1) % 7
        r = match(dow, w, 0, 6)
        if r is False: return False
    if dom != '*':
        r = match(dom, d.day, 1, 31)
        if r is False: return False
    return True

def job_hhmm(expr):
    p = (expr or '').split()
    if len(p) >= 2 and p[0].isdigit() and p[1].isdigit():
        return '%02d:%02d' % (int(p[1]), int(p[0]))
    if len(p) >= 2 and '/' in p[1]:
        try:
            step = p[1].split('/')[1].split()[0]
            return '每%s小时' % step
        except Exception:
            pass
    if len(p) >= 2 and p[1] == '*':
        return '每小时'
    return expr or '?'

def review_file(wsp, d):
    for name in (d.strftime('%Y-%m-%d')+'.md', d.strftime('%Y%m%d')+'.md'):
        f = os.path.join(wsp,'state','self-review',name)
        if os.path.exists(f):
            return f, os.path.getsize(f)
    return None, 0

def task_rows(days_back_done=1):
    db = os.path.join(STATE,'tasks','tasks.db')
    tmp = '/tmp/.butler-report-tasks.db'
    try:
        shutil.copyfile(db, tmp)
        c = sqlite3.connect(tmp)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute("select no,title,status,agent,closed_by,created,updated,due_plan,prio from tasks")]
        c.close()
        return rows
    except Exception:
        return []

def main():
    send = '--send' in sys.argv
    d = today(); y = d - datetime.timedelta(days=1)
    jobs, cron_src = load_cron()
    rows = task_rows()
    L = []
    L.append('【五大管家日报 · %s】' % d.strftime('%Y-%m-%d'))
    L.append('')
    L.append('一、昨天（%s）实际完成' % y.strftime('%m-%d'))
    missing = []
    for name, aid, wsp in BUTLERS:
        f, size = review_file(wsp, y)
        myjobs = jobs_of(jobs, aid)
        ran = []
        for j in myjobs:
            st = j.get('state') or {}
            ms = st.get('lastRunAtMs')
            if ms:
                dt = datetime.datetime.fromtimestamp(ms/1000)
                if dt.date() == y:
                    ran.append('%s %s' % (dt.strftime('%H:%M'), 'ok' if st.get('lastStatus')=='ok' else (st.get('lastStatus') or '?')))
        closed = [r for r in rows if r.get('status')=='done' and (r.get('agent')==aid or r.get('closed_by') in AGENT_ALIAS.get(aid,[]))
                  and (r.get('updated') or '')[:10] == y.strftime('%Y-%m-%d')]
        parts = []
        if f: parts.append('自审 %dB' % size)
        else:
            parts.append('自审 未产出')
            missing.append(name)
        if ran: parts.append('定时任务 ' + '、'.join(ran[:4]))
        parts.append('关单 %d' % len(closed))
        if closed: parts.append('如「%s」' % closed[0]['title'][:18])
        L.append('· %s：%s' % (name, '｜'.join(parts)))
    L.append('')
    L.append('二、今天（%s）计划' % d.strftime('%m-%d'))
    for name, aid, wsp in BUTLERS:
        myjobs = [j for j in jobs_of(jobs, aid) if j.get('enabled', True)]
        todays = []
        for j in myjobs:
            sch = j.get('schedule') or {}
            expr = sch.get('expr') or sch.get('cron') or ''
            st = j.get('state') or {}
            ms = st.get('nextRunAtMs')
            # 一次性任务看 nextRunAtMs；周期任务必须按表达式判断今天是否会跑
            # （nextRunAtMs 往往已滚到明天，用它判断今天会漏报）
            if (sch.get('kind') == 'at') or (not expr and ms):
                if ms:
                    nd = datetime.datetime.fromtimestamp(ms/1000)
                    if nd.date() == d:
                        todays.append('%s %s' % (nd.strftime('%H:%M'), j.get('name','')[:16]))
                continue
            if cron_fires_today(expr, d):
                todays.append('%s %s' % (job_hhmm(expr), j.get('name','')[:16]))
        todays.sort()
        pend = [r for r in rows if r.get('agent')==aid and r.get('status') in ('pending','in_progress')]
        line = '· %s：' % name
        line += ('；'.join(todays[:5]) if todays else '今天无定时任务')
        if pend: line += '；在办 %d 项（%s）' % (len(pend), pend[0]['title'][:16])
        L.append(line)
    L.append('')
    L.append('三、需要你知道的')
    if missing:
        L.append('· 昨日自审缺失：' + '、'.join(missing))
    else:
        L.append('· 昨日五家自审全部有产出')
    L.append('· 数据源：各家 state/self-review/、定时任务运行记录、任务账本（不含推测）')
    L.append('· cron 数据：%s' % cron_src)
    text = '\n'.join(L)
    if send:
        r = subprocess.run(['bash', os.path.join(WS,'tools','notify.sh'), text], capture_output=True, text=True)
        print('notify rc=%s %s' % (r.returncode, (r.stderr or r.stdout)[:120]))
    else:
        print(text)

if __name__ == '__main__':
    main()

