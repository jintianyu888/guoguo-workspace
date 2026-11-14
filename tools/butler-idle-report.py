#!/usr/bin/env python3
# butler-idle-report.py — 零 token 管家空转审计：谁 7 天没干活、谁有 cron 却没产出
import json, os, glob, subprocess, time, sys

HOME = '/home/j/.openclaw'
WS = HOME + '/workspace'
OUT = WS + '/state/work/butler-idle.json'
REG = HOME + '/state/agents-registry.json'

# 必须干活的核心（不许判空转）
CORE = {'main', 'maint', 'backup', 'model', 'work', 'library', 'news', 'print', 'tax', 'wealth'}

def sh(c):
    try:
        return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ''

def cron_counts():
    raw = sh('openclaw cron list --json')
    try:
        d = json.loads(raw)
        jobs = d.get('jobs') if isinstance(d, dict) else d
    except Exception:
        return {}
    cnt = {}
    for j in jobs or []:
        if not j.get('enabled', True):
            continue
        a = j.get('agentId') or 'main'
        cnt[a] = cnt.get(a, 0) + 1
    return cnt

def main():
    now = time.time()
    cmap = cron_counts()
    rows = []
    for d in sorted(glob.glob(HOME + '/agents/*/')):
        a = d.strip('/').split('/')[-1]
        files = [f for f in glob.glob(d + 'sessions/**/*', recursive=True)
                 if os.path.isfile(f) and '.deleted.' not in f]
        last = max([os.path.getmtime(f) for f in files], default=0)
        days = round((now - last) / 86400, 1) if last else 999
        rows.append({'agent': a, 'idle_days': days, 'cron': cmap.get(a, 0),
                     'core': a in CORE})
    idle = [r for r in rows if not r['core'] and r['cron'] == 0 and r['idle_days'] >= 7]
    orphan = [r for r in rows if not r['core'] and r['cron'] > 0 and r['idle_days'] >= 7]
    data = {'ts': int(now), 'total': len(rows),
            'idle_on_demand': idle, 'has_cron_but_silent': orphan,
            'cron_total': sum(cmap.values())}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, 'w'), ensure_ascii=False, indent=1)

    prev = {}
    try:
        prev = json.load(open(OUT + '.prev'))
    except Exception:
        pass
    prev_set = {r['agent'] for r in prev.get('idle_on_demand', [])}
    new_idle = [r['agent'] for r in idle if r['agent'] not in prev_set]

    first_run = not os.path.exists(OUT + '.prev')
    if new_idle and not first_run:
        msg = '【管家空转】新增 %d 个 7 天没干活且无 cron 的管家：%s（明细 state/work/butler-idle.json）' % (
            len(new_idle), '、'.join(new_idle[:8]))
        sh(WS + "/tools/notify.sh '" + msg.replace("'", "") + "'")
    try:
        json.dump(data, open(OUT + '.prev', 'w'), ensure_ascii=False)
    except Exception:
        pass
    print('total=%d idle_on_demand=%d has_cron_silent=%d cron_total=%d new=%d' % (
        len(rows), len(idle), len(orphan), data['cron_total'], len(new_idle)))
    for r in idle:
        print('  IDLE %-16s %6.1fd' % (r['agent'], r['idle_days']))
    for r in orphan:
        print('  SILENT(cron=%d) %-14s %6.1fd' % (r['cron'], r['agent'], r['idle_days']))

if __name__ == '__main__':
    main()
