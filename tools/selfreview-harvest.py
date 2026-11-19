#!/usr/bin/env python3
"""selfreview-harvest.py v1.0 (2026-11-19) —— 把五管家自审任务的**真实回复**捞回 self-review 文件

问题：自审 cron 提示词让 agent「直接在回复里输出」，但没有任何环节把回复写盘，
      结果 self-review-<date>.md 只有零 token 事实包，结论段永远空（11-18/11-19 实测）。
方案：cron 运行记录里本来就存了 summary（agent 回复全文，实测 6KB+），
      由本脚本统一收割并追加到各管家 state/self-review/，不再要求 agent 有写权限。

用法: python3 tools/selfreview-harvest.py [--date YYYY-MM-DD] [--dry-run]
"""
import json, os, subprocess, sys, datetime

W = '/home/j/.openclaw/workspace'
CLI = '/home/j/.npm-global/bin/openclaw'
STATE = W + '/state/butler/harvest-state.json'
MAP = {
    '管家每日自审-maint':   ('maint',   '/home/j/openclaw-workspaces/maint'),
    '管家每日自审-backup':  ('backup',  '/home/j/.openclaw/workspace-backup'),
    '管家每日自审-model':   ('model',   '/home/j/.openclaw/workspace-model'),
    '管家每日自审-work':    ('work',    '/home/j/openclaw-workspaces/work'),
    '管家每日自审-hermess': ('hermess', '/home/j/openclaw-workspaces/sheet-music'),
}


def jobs():
    r = subprocess.run([CLI, 'cron', 'list', '--json'], capture_output=True, text=True, timeout=120)
    d = json.loads(r.stdout)
    d = d if isinstance(d, list) else d.get('jobs', d)
    return d


def last_run(job_id):
    r = subprocess.run([CLI, 'cron', 'runs', '--id', job_id, '--limit', '4'],
                       capture_output=True, text=True, timeout=120)
    try:
        d = json.loads(r.stdout)
    except Exception:
        return None
    for e in d.get('entries', []):
        if e.get('status') == 'ok' and (e.get('summary') or '').strip():
            return e
    return None


WS_ALL = {
    'maint': '/home/j/openclaw-workspaces/maint',
    'backup': '/home/j/.openclaw/workspace-backup',
    'model': '/home/j/.openclaw/workspace-model',
    'work': '/home/j/openclaw-workspaces/work',
    'hermess': '/home/j/openclaw-workspaces/sheet-music',
}


def harvest_mutual(by_name, day, st, dry):
    """互审定稿-<管家>：回复收割到 主区 state/review/互审-<date>/<管家>.md"""
    n = 0
    for name, j in by_name.items():
        if not (name or '').startswith('互审定稿-'):
            continue
        aid = name.split('-', 1)[1]
        e = last_run(j.get('id'))
        if not e:
            print('SKIP 互审无成功运行:', name); continue
        ts = e.get('ts') or 0
        if datetime.date.fromtimestamp(ts / 1000).isoformat() != day:
            continue
        if st.get('mutual:' + aid) == ts:
            continue
        body = (e.get('summary') or '').strip()
        if len(body) < 120:
            print('SKIP 互审回复过短(%dB): %s' % (len(body), name)); continue
        d = os.path.join(W, 'state/review', '互审-%s' % day)
        pth = os.path.join(d, '%s.md' % aid)
        if dry:
            print('[dry] 互审 %s -> %s (+%dB)' % (name, pth, len(body))); continue
        os.makedirs(d, exist_ok=True)
        stamp = datetime.datetime.fromtimestamp(ts / 1000).strftime('%m-%d %H:%M')
        with open(pth, 'a') as f:
            f.write('\n## 互审意见（运行于 %s）\n%s\n' % (stamp, body))
        st['mutual:' + aid] = ts
        n += 1
        print('OK 互审 %s -> %s' % (name, pth))
    return n


def main():
    dry = '--dry-run' in sys.argv
    day = sys.argv[sys.argv.index('--date') + 1] if '--date' in sys.argv else datetime.date.today().isoformat()
    st = {}
    if os.path.exists(STATE):
        try: st = json.load(open(STATE))
        except Exception: st = {}
    by_name = {j.get('name'): j for j in jobs()}
    wrote = 0
    for name, (aid, ws) in MAP.items():
        j = by_name.get(name)
        if not j:
            print('SKIP 未找到任务:', name); continue
        e = last_run(j.get('id'))
        if not e:
            print('SKIP 无成功运行:', name); continue
        ts = e.get('ts') or 0
        day_of = datetime.date.fromtimestamp(ts / 1000).isoformat()
        if day_of != day:
            print('SKIP 最近成功跑的是 %s（非 %s）: %s' % (day_of, day, name)); continue
        key = name + '@' + str(ts)
        if st.get(aid) == ts:
            print('SKIP 已收割过:', name); continue
        body = (e.get('summary') or '').strip()
        if len(body) < 200:
            print('SKIP 回复过短(%dB): %s' % (len(body), name)); continue
        p = os.path.join(ws, 'state/self-review/self-review-%s.md' % day)
        txt = ''
        if os.path.exists(p):
            txt = open(p, errors='replace').read()
        marker = '<!-- harvest:%s -->' % ts
        if marker in txt:
            st[aid] = ts
            print('SKIP 文件里已有本轮:', name); continue
        stamp = datetime.datetime.fromtimestamp(ts / 1000).strftime('%m-%d %H:%M')
        block = ('\n\n## 结论（agent 自审 · 运行于 %s）\n%s\n%s\n' % (stamp, marker, body))
        if dry:
            print('[dry] %s -> %s (+%dB)' % (name, p, len(block))); continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'a').write(block)
        # v1.1 2026-11-19：互审任务要读 <对家>/state/reports/draft.md，但从来没人写这个文件，
        # 导致互审一律「对家草稿未就绪」。这里把自审结论同时落成 draft.md，互审才有东西可审。
        try:
            rd = os.path.join(ws, 'state/reports')
            os.makedirs(rd, exist_ok=True)
            open(os.path.join(rd, 'draft.md'), 'w').write(
                '# 今日自审草稿 %s（harvested %s）\n\n%s\n' % (day, stamp, body))
        except Exception as _e:
            print('draft.md 写入失败:', _e)
        st[aid] = ts
        wrote += 1
        print('OK 收割 %s -> %s (+%dB)' % (name, p, len(block)))
    if not dry:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(st, open(STATE, 'w'), ensure_ascii=False, indent=1)
    # 缺口语义：13:15/13:25 两轮后仍有管家没结论 -> 进夜间汇总，别静默
    try:
        now = datetime.datetime.now()
        if now.hour >= 13 and now.minute >= 25:
            missing = []
            for name, (aid, ws) in MAP.items():
                fp = os.path.join(ws, 'state/self-review/self-review-%s.md' % day)
                t = open(fp, errors='replace').read() if os.path.exists(fp) else ''
                if '## 结论' not in t: missing.append(aid)
            if missing:
                msg = '自审结论仍缺：' + '、'.join(missing) + '（13:25 收割后仍无结论段，需排查该管家自审任务）'
                print(msg)
                subprocess.run(['bash', W + '/tools/notify.sh', '--digest', msg], timeout=120)
    except Exception as ex:
        print('缺口检查失败:', ex)
    wrote += harvest_mutual(by_name, day, st, dry)
    print('完成，本次写入 %d 份' % wrote)
    return 0


if __name__ == '__main__':
    sys.exit(main())
