#!/usr/bin/env python3
"""overview-health.py —— 上帝视角：六域健康聚合（零 token，全本地探针）

原则：每个指标必须来自真实动作（HTTP 请求 / 真实写库 / 文件 mtime / 进程状态），
取不到就写「未采集」，禁止拿「服务在跑」当健康。输出 state/overview/health.json。

用: run           采集并打印
    json         只输出 JSON
"""
import json, os, re, sys, time, socket, sqlite3, subprocess, datetime, urllib.request

WS = '/home/j/.openclaw/workspace'
OUTD = os.path.join(WS, 'state/overview')
GW = 'http://127.0.0.1:18789/health'
WARN_DAYS = {'backup': 2, 'face': 2}

def now():
    return datetime.datetime.now().strftime('%F %T')

def sh(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or '').strip(), (r.stderr or '').strip()
    except subprocess.TimeoutExpired:
        return 124, '', 'timeout'
    except Exception as e:
        return 1, '', str(e)[:80]

def http(url, timeout=3):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'guoguo-overview/1'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except Exception:
        return 0

def lvl(worst):
    return worst

# ---------- 1 服务 ----------
def d_service():
    det, bad = [], False
    rc, out, _ = sh("systemctl --user show openclaw-gateway -p ActiveState -p MainPID -p NRestarts --value")
    parts = [x for x in out.split('\n') if x]
    state = parts[0] if parts else 'unknown'
    pid = parts[1] if len(parts) > 1 else '-'
    nrs = parts[2] if len(parts) > 2 else '-'
    det.append('systemd=%s pid=%s NRestarts=%s' % (state, pid, nrs))
    if state != 'active':
        bad = True
    code = http(GW)
    det.append('health HTTP=%s' % code)
    if code != 200:
        bad = True
    # 真实写探针：真写一次库
    try:
        c = sqlite3.connect(os.path.join(WS, 'state/tasks/tasks.db'), timeout=5)
        c.execute('create table if not exists _probe(id integer, ts text)')
        c.execute('insert into _probe values(1,?)', (now(),))
        c.execute('delete from _probe where id=1')
        c.commit(); c.close()
        det.append('DB 真实写探针=通过')
    except Exception as e:
        det.append('DB 真实写探针=失败(%s)' % str(e)[:40]); bad = True
    return {'level': 'bad' if bad else 'ok', 'headline': '网关' + ('异常' if bad else '正常'), 'details': det, 'source': 'systemd+HTTP+sqlite'}

# ---------- 2 任务 ----------
def d_tasks():
    det, w = [], 'ok'
    try:
        c = sqlite3.connect(os.path.join(WS, 'state/tasks/tasks.db'), timeout=5)
        nows = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        over = c.execute("select count(*) from tasks where status in ('pending','in_progress') and due_plan is not null and due_plan<>'' and due_plan<?", (nows,)).fetchone()[0]
        op = c.execute("select count(*) from tasks where status in ('pending','in_progress')").fetchone()[0]
        wait = c.execute("select count(*) from tasks where status in ('pending','in_progress') and wait_user=1").fetchone()[0]
        det.append('未完成 %d（等你 %d）· 逾期 %d' % (op, wait, over))
        if over >= 3:
            w = 'warn'
        c.close()
    except Exception as e:
        det.append('tasks.db 读取失败 %s' % str(e)[:40]); w = 'unknown'
    try:
        c = sqlite3.connect('/home/j/.openclaw/state/openclaw.sqlite', timeout=5)
        since = int((time.time() - 86400) * 1000)
        rows = c.execute("select status,count(*) n from cron_run_receipts where started_at_ms>=? group by status", (since,)).fetchall()
        tot = sum(r[1] for r in rows)
        fail = sum(r[1] for r in rows if r[0] != 'ok')
        rate = (100.0 * (tot - fail) / tot) if tot else 0
        det.append('定时任务 24h %d 跑 %d 败 = %.1f%%' % (tot, fail, rate))
        if tot and rate < 95:
            w = 'warn' if w == 'ok' else w
        c.close()
    except Exception as e:
        det.append('cron 回执读取失败 %s' % str(e)[:40])
    return {'level': w, 'headline': ('逾期 %d' % over) if 'over' in dir() else '任务', 'details': det, 'source': 'tasks.db+cron_run_receipts'}

# ---------- 3 资金 ----------
def d_money():
    det, w = [], 'ok'
    avail = None
    p = os.path.join(WS, 'state/model-econ/balances.json')
    try:
        age = (time.time() - os.path.getmtime(p)) / 3600
        d = json.load(open(p, encoding='utf-8'))
        prov = d.get('providers') or {}
        ds = prov.get('deepseek') or {}
        avail = ds.get('available') or ds.get('balance')
        det.append('deepseek 可用 %s' % (avail if avail not in (None, '') else '未采集'))
        det.append('快照 %.1f 小时前' % age)
        if age > 12:
            w = 'warn'; det.append('快照过旧（>12h）')
        if isinstance(avail, (int, float)) and avail < 30:
            w = 'warn'; det.append('余额偏低')
        for name in ('kimi', 'zai', 'qianwen-token-plan'):
            q = prov.get(name) or {}
            if q:
                det.append('%s: %s' % (name, json.dumps({k: q[k] for k in list(q)[:2]}, ensure_ascii=False)))
    except Exception as e:
        w = 'unknown'; det.append('余额读取失败 %s' % str(e)[:40])
    head = '资金'
    try:
        head = 'deepseek ¥%s' % avail if isinstance(avail, (int, float)) else '资金'
    except Exception:
        pass
    return {'level': w, 'headline': head, 'details': det, 'source': 'model-econ/balances.json'}

# ---------- 4 存储 ----------
def d_storage():
    det, w = [], 'ok'
    for path, label in (('/', '根盘'), ('/mnt/d', 'D'), ('/mnt/e', 'E'), ('/mnt/h', 'H'), ('/mnt/nas', 'NAS')):
        if not os.path.ismount(path) and path != '/':
            det.append('%s 未挂载' % label)
            if label in ('E', 'NAS'):
                w = 'warn'
            continue
        rc, out, _ = sh("df -P %s | tail -1 | awk '{print $5, $4}'" % path, 5)
        if rc == 0 and out:
            pct, avail = out.split()
            det.append('%s 用 %s（余 %s KB）' % (label, pct, avail))
            if pct.rstrip('%').isdigit() and int(pct.rstrip('%')) >= 88:
                w = 'warn'
    try:
        best, newest = None, 0
        for base in ('/mnt/e/openclaw-backups', '/mnt/d/openclaw-backups'):
            if not os.path.isdir(base):
                continue
            for f in os.listdir(base):
                if f.endswith('.tar.gz'):
                    m = os.path.getmtime(os.path.join(base, f))
                    if m > newest:
                        newest, best = m, f
        if best:
            age = (time.time() - newest) / 86400
            det.append('最新归档 %s（%.1f 天前）' % (best[:26], age))
            if age > WARN_DAYS['backup']:
                w = 'warn'; det.append('归档偏旧')
        else:
            det.append('未找到归档'); w = 'warn'
    except Exception as e:
        det.append('归档检查失败 %s' % str(e)[:40])
    head = '存储'
    try:
        worst = max([x for x in det if ' 用 ' in x], key=lambda s: int(re.search(r'用 (\d+)%', s).group(1)), default=None)
        if worst:
            m = re.search(r'(\S+) 用 (\d+)%', worst)
            head = '最紧 %s %s%%' % (m.group(1), m.group(2))
    except Exception:
        pass
    return {'level': w, 'headline': head, 'details': det, 'source': 'df+归档 mtime'}

# ---------- 5 安防 ----------
def d_security():
    det, w = [], 'ok'
    code = http('http://192.168.1.103/', 3)
    det.append('NVR HTTP=%s' % code)
    if code == 0:
        w = 'warn'
    for p, label in (('state/work/nvr-isapi.log', 'NVR 日扫'), ('state/work/nvr-face.log', '人脸扫描'), ('state/work/news-brief.log', '新闻')):
        fp = os.path.join(WS, p)
        if os.path.exists(fp):
            age = (time.time() - os.path.getmtime(fp)) / 3600
            det.append('%s 日志 %.1f 小时前' % (label, age))
            if age > 30:
                w = 'warn' if w == 'ok' else w
        else:
            det.append('%s 日志 未采集' % label)
    try:
        c = sqlite3.connect(os.path.join(WS, 'state/alerts/alerts.db'), timeout=5)
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        n = c.execute("select count(*) from events where ts>=?", (today,)).fetchone()[0]
        p0 = c.execute("select count(*) from events where ts>=? and (raw like '%P0%' or kind like '%P0%')", (today,)).fetchone()[0]
        det.append('今日告警 %d 条（其中标 P0 %d）' % (n, p0))
        c.close()
    except Exception as e:
        det.append('告警库 未采集(%s)' % str(e)[:30])
    return {'level': w, 'headline': ('NVR 在线' if code == 200 else 'NVR 不可达'), 'details': det, 'source': 'NVR HTTP+日志 mtime+alerts.db'}

# ---------- 6 模型 ----------
def d_model():
    det, w = [], 'ok'
    rc, out, err = sh("cd %s && timeout 40 python3 tools/modelchain-check.py 2>&1 | tail -3" % WS, 60)
    line = (out or err).split('\n')[-1] if (out or err) else ''
    det.append('模型链体检 rc=%d %s' % (rc, line[:70]))
    if rc != 0:
        w = 'warn'
    code = http('http://127.0.0.1:11434/api/tags', 3)
    det.append('本地 ollama 代理 HTTP=%s' % code)
    if code == 0:
        w = 'warn' if w == 'ok' else w
    return {'level': w, 'headline': ('模型链 OK' if rc == 0 else '模型链有悬空'), 'details': det, 'source': 'modelchain-check+ollama'}

def run():
    doms = [('服务', d_service), ('任务', d_tasks), ('资金', d_money),
            ('存储', d_storage), ('安防', d_security), ('模型', d_model)]
    out = {'generated_at': now(), 'domains': {}}
    for name, fn in doms:
        try:
            r = fn()
        except Exception as e:
            r = {'level': 'unknown', 'headline': name, 'details': ['采集异常 %s' % str(e)[:60]], 'source': '-'}
        r['name'] = name
        out['domains'][name] = r
    bad = [k for k, v in out['domains'].items() if v['level'] == 'bad']
    warn = [k for k, v in out['domains'].items() if v['level'] == 'warn']
    out['summary'] = {'bad': bad, 'warn': warn,
                      'verdict': 'bad' if bad else ('warn' if warn else 'ok')}
    os.makedirs(OUTD, exist_ok=True)
    p = os.path.join(OUTD, 'health.json')
    tmp = p + '.tmp'
    json.dump(out, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return out

def main():
    o = run()
    if 'json' in sys.argv:
        print(json.dumps(o, ensure_ascii=False, indent=1))
        return
    icon = {'ok': '🟢', 'warn': '🟡', 'bad': '🔴', 'unknown': '⚪'}
    print('上帝视角 · %s  总判 %s' % (o['generated_at'], icon[o['summary']['verdict']]))
    for name, d in o['domains'].items():
        print('%s %s  %s' % (icon[d['level']], name, d['headline']))
        for x in d['details']:
            print('    ' + x)

if __name__ == '__main__':
    main()
