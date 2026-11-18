#!/usr/bin/env python3
# alert-digest.py v1.0 (2026-11-18) —— 每晚把当日 P1 告警压成一条汇总，只发一条；发完归档
# 用法: python3 tools/alert-digest.py [--dry-run]
import json, os, subprocess, sys, datetime, collections, shutil

WS = '/home/j/.openclaw/workspace'
Q = WS + '/state/alerts/digest.jsonl'
today = datetime.date.today().isoformat()


def headline(t):
    line = (t or '').split('\n')[0].strip()
    return line[:58]


def main():
    dry = '--dry-run' in sys.argv
    rows = []
    if os.path.exists(Q):
        for line in open(Q):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if (r.get('ts') or '')[:10] == today:
                rows.append(r)
    if not rows:
        print('今日无 P1 告警')
        return 0
    groups = collections.Counter()
    samples = {}
    for r in rows:
        h = headline(r.get('text'))
        groups[h] += 1
        samples.setdefault(h, r.get('text'))
    lines = ['📋 今日次要告警汇总 %d 条（只报重要的，其余进这里）' % len(rows)]
    for h, n in groups.most_common(10):
        lines.append('· %s%s' % (h, ('（×%d）' % n) if n > 1 else ''))
    if len(groups) > 10:
        lines.append('· …另有 %d 类' % (len(groups) - 10))
    lines.append('明细 state/alerts/digest.jsonl；只有 P0 会即时推')
    msg = '\n'.join(lines)
    print(msg)
    if dry:
        return 0
    r = subprocess.run(['bash', WS + '/tools/notify.sh', msg], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print('发送失败:', (r.stderr or r.stdout)[:200])
        return 1
    arch = WS + '/state/alerts/digest-archive-%s.jsonl' % today.replace('-', '')
    with open(arch, 'a') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    open(Q, 'w').close()
    print('已发并归档 %d 条' % len(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
