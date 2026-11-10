#!/usr/bin/env python3
"""skill-audit.py —— 技能库盘点与退休判定（零 token）

解决：光看 usage.jsonl 无法判断「45 天没用」，因为新建技能的首次见到时间没记。
本工具维护 state/skills/registry.jsonl（只追加 first_seen），
未使用天数 = 今天 - max(first_seen, 最后一次使用)。

用法：
  python3 tools/skill-audit.py            # 全量盘点
  python3 tools/skill-audit.py --retire   # 只列 45 天退休候选
  python3 tools/skill-audit.py --json
"""
import json, os, sys, time, hashlib

W = '/home/j/.openclaw/workspace'
SHARED = '/home/j/.openclaw/shared-skills'
WORKSHOP = '/home/j/.openclaw/agents/main/agent/workshop-skills'
USAGE = os.path.join(W, 'state/skills/usage.jsonl')
REG = os.path.join(W, 'state/skills/registry.jsonl')
RETIRE_DAYS = 45
WATCH_DAYS = 30


def today():
    return time.strftime('%Y-%m-%d')


def load_registry():
    reg = {}
    if not os.path.exists(REG):
        return reg
    with open(REG, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            n = o.get('skill')
            if n and n not in reg:
                reg[n] = o.get('first_seen') or today()
    return reg


def save_registry(reg):
    os.makedirs(os.path.dirname(REG), exist_ok=True)
    known = load_registry()
    add = []
    for n, d in reg.items():
        if n not in known:
            add.append({'skill': n, 'first_seen': d, 'recorded': time.strftime('%Y-%m-%dT%H:%M:%S')})
    if add:
        with open(REG, 'a', encoding='utf-8') as f:
            for o in add:
                f.write(json.dumps(o, ensure_ascii=False) + chr(10))
    return [a['skill'] for a in add]


def load_usage():
    u = {}
    if not os.path.exists(USAGE):
        return u
    with open(USAGE, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            n = o.get('skill')
            if not n:
                continue
            d = u.setdefault(n, {'ok': 0, 'fail': 0, 'partial': 0, 'last': None, 'notes': []})
            oc = o.get('outcome', 'ok')
            if oc in d:
                d[oc] += 1
            ts = o.get('ts') or ''
            if ts and (not d['last'] or ts > d['last']):
                d['last'] = ts
            if o.get('note'):
                d['notes'].append(o['note'])
    return u


def days_between(a, b):
    try:
        ta = time.mktime(time.strptime(a[:10], '%Y-%m-%d'))
        tb = time.mktime(time.strptime(b[:10], '%Y-%m-%d'))
        return int((tb - ta) // 86400)
    except Exception:
        return 0


def skill_dirs():
    out = {}
    if os.path.isdir(SHARED):
        for n in sorted(os.listdir(SHARED)):
            p = os.path.join(SHARED, n, 'SKILL.md')
            if os.path.isfile(p):
                out[n] = p
    return out


def md5(p):
    try:
        with open(p, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except Exception:
        return ''


def main():
    args = sys.argv[1:]
    as_json = '--json' in args
    only_retire = '--retire' in args
    now = today()
    reg = load_registry()
    skills = skill_dirs()
    usage = load_usage()

    # 新技能首次见到 = 今天
    for n in skills:
        reg.setdefault(n, now)
    new = save_registry(reg)

    rows = []
    for n in skills:
        u = usage.get(n, {})
        last = u.get('last')
        anchor = max(reg[n], (last or '')[:10])
        idle = days_between(anchor, now)
        uses = (u.get('ok', 0) + u.get('fail', 0) + u.get('partial', 0))
        fails = u.get('fail', 0)
        # 漂移：共享主本 vs main 实际加载副本
        ws = os.path.join(WORKSHOP, n, 'SKILL.md')
        drift = 'same'
        if os.path.isfile(ws):
            drift = 'same' if md5(ws) == md5(skills[n]) else 'stale'
        else:
            drift = 'absent'
        rows.append({
            'skill': n, 'first_seen': reg[n], 'last_used': last,
            'uses': uses, 'fails': fails, 'idle_days': idle, 'workshop': drift,
        })

    # 45 天没用就是候选（用过也要看，长期不用的技能同样是债）
    retire = [r for r in rows if r['idle_days'] >= RETIRE_DAYS]
    watch = [r for r in rows if WATCH_DAYS <= r['idle_days'] < RETIRE_DAYS]
    used = [r for r in rows if r['uses'] > 0]
    never = [r for r in rows if r['uses'] == 0]
    drift = [r for r in rows if r['workshop'] == 'stale']
    absent = [r for r in rows if r['workshop'] == 'absent']
    failing = [r for r in rows if r['fails'] >= 2 and r['fails'] / max(r['uses'], 1) >= 0.34]

    if as_json:
        print(json.dumps({
            'date': now, 'total': len(rows), 'retire': retire, 'watch': watch,
            'never_used': len(never), 'used': len(used), 'drift': drift,
            'absent_in_workshop': absent, 'failing': failing, 'new_today': new,
            'rows': rows,
        }, ensure_ascii=False, indent=1))
        return 0

    if only_retire:
        if not retire:
            print('无 45 天退休候选（技能库首次见到日：最早 %s）' % min(reg.values()))
        for r in retire:
            print('退休候选 %s（%d 天未用，从未使用）' % (r['skill'], r['idle_days']))
        return 0

    print('技能库盘点 %s' % now)
    print('总数 %d ｜ 用过 %d ｜ 从未使用 %d ｜ 本次新登记 %d' % (
        len(rows), len(used), len(never), len(new)))
    print('')
    print('▍45 天退休候选：%d' % len(retire))
    for r in retire:
        print('  - %s（%d 天）' % (r['skill'], r['idle_days']))
    print('▍30-45 天观察：%d' % len(watch))
    for r in watch:
        print('  - %s（%d 天）' % (r['skill'], r['idle_days']))
    print('▍使用表现')
    if used:
        for r in sorted(used, key=lambda x: -x['uses']):
            print('  - %s：%d 次，失败 %d' % (r['skill'], r['uses'], r['fails']))
    else:
        print('  （仅 %d 条使用记录）' % len(usage))
    if failing:
        print('▍该补坑：%s' % ', '.join(r['skill'] for r in failing))
    print('▍同步状态')
    print('  - main 副本过期 %d 个：%s' % (len(drift), ', '.join(r['skill'] for r in drift) or '无'))
    print('  - main 缺副本 %d 个：%s' % (len(absent), ', '.join(r['skill'] for r in absent) or '无'))
    print('▍首次退休审查日：%s（最早技能首见 %s + %d 天）' % (
        time.strftime('%Y-%m-%d', time.localtime(
            time.mktime(time.strptime(min(reg.values()), '%Y-%m-%d')) + RETIRE_DAYS * 86400)),
        min(reg.values()), RETIRE_DAYS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
