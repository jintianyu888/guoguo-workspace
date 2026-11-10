#!/usr/bin/env python3
"""skill-selftest.py —— 技能自检执行器（零 token）

约定：技能目录下放 selftest.sh，rc=0 表示这份技能现在真的能用。
没有 selftest.sh 的技能记 skip（不算失败，只在报告里标出来）。

用法：
  python3 tools/skill-selftest.py [--json] [--only name1,name2]

结果追加到 state/skills/selftest.jsonl，供 skill-maintain 汇总。
"""
import json, os, subprocess, sys, time

W = '/home/j/.openclaw/workspace'
SHARED = '/home/j/.openclaw/shared-skills'
LOG = os.path.join(W, 'state/skills/selftest.jsonl')
TIMEOUT = 45


def main():
    args = sys.argv[1:]
    as_json = '--json' in args
    only = None
    for i, a in enumerate(args):
        if a == '--only' and i + 1 < len(args):
            only = set(x.strip() for x in args[i + 1].split(',') if x.strip())

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    stamp = time.strftime('%Y-%m-%dT%H:%M:%S')
    rows = []
    if not os.path.isdir(SHARED):
        print('共享技能目录不存在'); return 2
    for name in sorted(os.listdir(SHARED)):
        d = os.path.join(SHARED, name)
        if name.startswith('.') or not os.path.isdir(d):
            continue
        if only and name not in only:
            continue
        script = os.path.join(d, 'selftest.sh')
        if not os.path.isfile(script):
            rows.append({'skill': name, 'result': 'skip', 'note': 'no selftest.sh'})
            continue
        t0 = time.time()
        try:
            p = subprocess.run(['bash', script], cwd=d, capture_output=True,
                               text=True, timeout=TIMEOUT)
            rc = p.returncode
            out = (p.stdout or '') + (p.stderr or '')
        except subprocess.TimeoutExpired:
            rc, out = 124, 'timeout %ds' % TIMEOUT
        except Exception as e:
            rc, out = 1, 'error: %s' % e
        tail = ' '.join(out.strip().splitlines()[-2:])[:200]
        rows.append({'skill': name, 'result': 'pass' if rc == 0 else 'fail',
                     'rc': rc, 'note': tail,
                     'secs': round(time.time() - t0, 1)})

    with open(LOG, 'a', encoding='utf-8') as f:
        for r in rows:
            o = dict(r); o['ts'] = stamp
            f.write(json.dumps(o, ensure_ascii=False) + chr(10))

    bad = [r for r in rows if r['result'] == 'fail']
    ran = [r for r in rows if r['result'] != 'skip']
    if as_json:
        print(json.dumps({'ts': stamp, 'ran': len(ran), 'failed': bad,
                          'skipped': len(rows) - len(ran)}, ensure_ascii=False, indent=1))
    else:
        print('技能自检 %s：跑 %d 个，通过 %d，失败 %d，未覆盖 %d' % (
            stamp, len(ran), len(ran) - len(bad), len(bad), len(rows) - len(ran)))
        for r in bad:
            print('  ❌ %s（rc=%s）：%s' % (r['skill'], r.get('rc'), r.get('note')))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
