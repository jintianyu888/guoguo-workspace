#!/usr/bin/env python3
# verify-nightly.py v1.0 (2026-11-19) —— 22:00 验收：21:42/21:45 两个修复任务是否跑通
import json, subprocess, sys

CLI = '/home/j/.npm-global/bin/openclaw'
W = '/home/j/.openclaw/workspace'
TARGETS = ('每日用量快照', '晚间核查')


def main():
    r = subprocess.run([CLI, 'cron', 'list', '--json'], capture_output=True, text=True, timeout=120)
    try:
        d = json.loads(r.stdout)
    except Exception:
        print('cron list 解析失败'); return 2
    jobs = d if isinstance(d, list) else d.get('jobs', d)
    lines, bad = [], 0
    for j in jobs:
        n = j.get('name') or ''
        if not any(t in n for t in TARGETS):
            continue
        st = j.get('state') or {}
        status = st.get('lastRunStatus')
        lines.append('%s=%s' % (n, status))
        if status != 'ok':
            bad += 1
    msg = '夜间验收 21:42/21:45：' + ('；'.join(lines) if lines else '未找到任务')
    if bad:
        msg += '（仍有 %d 项未通过，明早排查）' % bad
    else:
        msg += '（全部通过，告警应自动清零）'
    print(msg)
    subprocess.run(['bash', W + '/tools/notify.sh', '--digest', msg], timeout=120)
    return 0


if __name__ == '__main__':
    sys.exit(main())
