#!/usr/bin/env python3
# activity-watch.py —— 每 2 分钟感知「备份 / 镜像 / 升级 / 重启」，写统一状态 + 关键节点飞书（零 token）
import json, os, re, subprocess, sys, time

WS = '/home/j/.openclaw/workspace'
ACT = os.path.join(WS, 'tools/activity.py')
LOG = os.path.join(WS, 'state/work/bk-run.log')
MARK = os.path.join(WS, 'state/work/.restart-in-progress')
EV = os.path.join(WS, 'state/status/activity-events.json')
NOTIFY = os.path.join(WS, 'tools/notify.sh')

# 进程特征 -> (kind, 名称, 预计分钟)
JOBS = [
    ('upgrade-panel.sh',        'upgrade', '版本升级',       20),
    ('upgrade-openclaw.sh',     'upgrade', '版本升级',       20),
    ('daily-backup.sh',         'backup',  '全量备份',      150),
    ('tier1-launch.sh',         'backup',  'T1 关键备份',    60),
    ('backup-tier1-critical.sh','backup',  'T1 关键备份',    60),
    ('tier2-launch.sh',         'backup',  'T2 中间备份',    90),
    ('backup-tier2-medium.sh',  'backup',  'T2 中间备份',    90),
    ('backup-drill.sh',         'backup',  '备份恢复演练',   60),
    ('backup-drill-nightly.sh', 'backup',  '备份恢复演练',   60),
    ('align-backup-triple.sh',  'mirror',  '备份镜像对齐',  120),
    ('backup-copy-verify.py',   'mirror',  '备份镜像校验',  120),
]

def sh(c):
    try:
        return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return ''

def act(*args):
    return sh(ACT + ' ' + ' '.join(args))

def cur_state():
    try:
        return json.loads(sh(ACT + ' get') or '{}')
    except Exception:
        return {}

def load_ev():
    try:
        return json.load(open(EV))
    except Exception:
        return {}

def save_ev(o):
    os.makedirs(os.path.dirname(EV), exist_ok=True)
    tmp = EV + '.tmp'
    json.dump(o, open(tmp, 'w'))
    os.replace(tmp, EV)

def notify(msg, alert=False):
    cmd = NOTIFY + (' --alert ' if alert else ' ') + shlex_q(msg)
    sh(cmd)

def shlex_q(s):
    return "'" + s.replace("'", "'\\''") + "'"

def proc_table():
    """返回第一个命中的 job（已排除自己）"""
    me = os.getpid()
    out = sh("pgrep -af 'daily-backup[.]sh|tier1-launch[.]sh|tier2-launch[.]sh|backup-tier[12]|align-backup-triple[.]sh|backup-copy-verify[.]py|backup-drill|upgrade-panel[.]sh|upgrade-openclaw[.]sh'")
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid = line.split(' ', 1)[0]
        if pid.isdigit() and int(pid) == me:
            continue
        if 'activity-watch' in line or 'pgrep' in line:
            continue
        for pat, kind, name, eta in JOBS:
            if pat in line:
                return {'pid': int(pid), 'kind': kind, 'name': name, 'eta': eta}
    return None

STAGES = [
    (r'1/5', 8), (r'2/5', 22), (r'3/5', 45), (r'4\.5/5', 88),
    (r'4/5', 60), (r'5/5', 95),
]

def backup_stage():
    tail = sh('tail -c 4000 ' + LOG + ' 2>/dev/null')
    pct, phase = None, ''
    for pat, val in STAGES:
        if re.search(pat, tail):
            pct = val
    lines = [l for l in tail.splitlines() if l.strip()]
    phase = re.sub(r'[\d\-]+ ', '', lines[-1])[:60] if lines else ''
    return pct, phase

def main():
    ev = load_ev()
    t = int(time.time())
    cur = cur_state()

    # 1) 重启中
    if os.path.exists(MARK):
        try:
            mt = int(os.path.getmtime(MARK))
        except Exception:
            mt = t
        if t - mt < 1200:
            el = int((t - mt) / 60)
            act("set kind=restart phase=网关重启中 percent=%d note=已 %d 分钟，通常 1-2 分钟" % (min(90, 30 + el * 10), el))
            return
        os.remove(MARK) if os.path.exists(MARK) else None

    job = proc_table()
    if job:
        kind, name, eta = job['kind'], job['name'], job['eta']
        started = cur.get('started_at') if cur.get('kind') == kind else None
        if not started:
            started = t
            notify('【%s 开始】正在跑，面板屏幕中央会显示进度，预计 %d 分钟内完成。' % (name, eta))
        el = int((t - started) / 60)
        pct, phase = (None, '')
        if kind == 'backup':
            pct, phase = backup_stage()
        if pct is None:
            pct = max(3, min(92, int(el / max(eta, 1) * 100)))
        note = '已运行 %d 分钟' % el
        if eta and el < eta:
            note += '，预计还剩约 %d 分钟' % (eta - el)
        act('set kind=%s phase=%s percent=%d note=%s' % (kind, (phase or name), pct, note))
        return

    # 2) 没进程了
    if cur.get('kind') in ('backup', 'mirror', 'upgrade'):
        if '演示' in (cur.get('note') or ''):
            return
        was = cur.get('kind')
        act('clear')
        if ev.get('kind') != was:
            save_ev({'kind': was, 'ended': t})
        else:
            ev['ended'] = t
            save_ev(ev)
        notify('【%s 结束】面板已恢复正常，细节看日志。' % {'backup': '备份', 'mirror': '镜像同步', 'upgrade': '升级'}.get(was, was))
        return

    if cur.get('kind') and '演示' not in (cur.get('note') or ''):
        act('clear')

if __name__ == '__main__':
    main()
