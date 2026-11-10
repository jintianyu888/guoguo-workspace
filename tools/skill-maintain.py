#!/usr/bin/env python3
"""skill-maintain.py —— 技能库每日自动体检 + 自愈 + 告警（零 token）

每天跑一次，做四件事：
  1. 自愈：共享主本 → main 加载副本镜像；补登记 first_seen
  2. 体检：skill-lint（结构/引用失效）+ skill-audit（45 天退休/漂移）
  3. 实测：跑每个技能的 selftest.sh（能跑的才算真能用）
  4. 告警：只报「新增或变化」的问题，周日附全量摘要；不刷屏

用法：
  python3 tools/skill-maintain.py [--dry] [--force-notify]
"""
import json, os, subprocess, sys, time

W = '/home/j/.openclaw/workspace'
SHARED = '/home/j/.openclaw/shared-skills'
S = os.path.join(W, 'state/skills')
HEALTH = os.path.join(S, 'health.json')
NOTIFY = os.path.join(W, 'tools/notify.sh')


def run(cmd, timeout=180):
    try:
        p = subprocess.run(cmd, cwd=W, capture_output=True, text=True, timeout=timeout,
                           shell=isinstance(cmd, str))
        return p.returncode, (p.stdout or '') + (p.stderr or '')
    except Exception as e:
        return 99, 'error: %s' % e


def load(p, default):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return default


def main():
    args = sys.argv[1:]
    dry = '--dry' in args
    force = '--force-notify' in args
    os.makedirs(S, exist_ok=True)
    stamp = time.strftime('%Y-%m-%dT%H:%M:%S')

    actions = []
    rc, out = run(['bash', 'tools/skill-mirror.sh'])
    if rc == 0:
        actions.append(out.strip())
    else:
        actions.append('镜像失败 rc=%d' % rc)

    # 体检
    rcl, outl = run(['python3', 'tools/skill-lint.py', '--json'])
    lint = load_str(outl, {})
    # 新技能自动补一份通用自检（已有 selftest.sh 的不动）
    rcb, outb = run(['python3', 'tools/skill-bootstrap-tests.py'])
    if rcb == 0 and outb.strip():
        actions.append(outb.strip().splitlines()[0])
    # 实测
    rct, outt = run(['python3', 'tools/skill-selftest.py', '--json'])
    test = load_str(outt, {})
    # 盘点
    rca, outa = run(['python3', 'tools/skill-audit.py', '--json'])
    audit = load_str(outa, {})

    issues = []
    for r in lint.get('errors') or []:
        issues.append({'kind': 'lint', 'skill': r.get('skill'),
                       'detail': '；'.join(r.get('errors') or [])})
    for r in test.get('failed') or []:
        issues.append({'kind': 'test', 'skill': r.get('skill'),
                       'detail': r.get('note') or 'rc=%s' % r.get('rc')})
    for r in audit.get('retire') or []:
        issues.append({'kind': 'retire', 'skill': r.get('skill'),
                       'detail': '%d 天未用（从未使用）' % r.get('idle_days', 0)})
    for r in audit.get('drift') or []:
        issues.append({'kind': 'drift', 'skill': r.get('skill'),
                       'detail': '执行副本与主本不一致'})

    # 共享主本可见性：extraDirs 被网关回写丢掉时，除 main 外的管家看不到这些技能
    try:
        cfg = json.load(open('/home/j/.openclaw/openclaw.json', encoding='utf-8'))
        dirs = ((cfg.get('skills') or {}).get('load') or {}).get('extraDirs') or []
        if os.path.abspath(SHARED) not in [os.path.abspath(d) for d in dirs]:
            issues.append({'kind': 'config', 'skill': 'skills.load.extraDirs',
                           'detail': '共享技能目录未挂载，其他管家看不到'})
    except Exception as e:
        issues.append({'kind': 'config', 'skill': 'openclaw.json',
                       'detail': '读配置失败：%s' % e})

    prev = load(HEALTH, {})
    prev_keys = set('%s|%s' % (i.get('kind'), i.get('skill')) for i in (prev.get('issues') or []))
    new_issues = [i for i in issues if '%s|%s' % (i['kind'], i['skill']) not in prev_keys]
    fixed = [k for k in prev_keys if k not in set('%s|%s' % (i['kind'], i['skill']) for i in issues)]

    cur = {
        'ts': stamp,
        'total': audit.get('total', 0),
        'lint_errors': len(lint.get('errors') or []),
        'lint_warnings': len(lint.get('warnings') or []),
        'selftest_ran': test.get('ran', 0),
        'selftest_failed': len(test.get('failed') or []),
        'uncovered': test.get('skipped', 0),
        'retire_candidates': len(audit.get('retire') or []),
        'drift': len(audit.get('drift') or []),
        'issues': issues,
        'fixed': fixed,
        'actions': actions,
    }
    if not dry:
        json.dump(cur, open(HEALTH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    weekly = time.localtime().tm_wday == 6
    lines = []
    if new_issues:
        lines.append('▍技能库 · 新问题 %d' % len(new_issues))
        for i in new_issues[:8]:
            lines.append('· %s（%s）：%s' % (i['skill'], i['kind'], i['detail'][:80]))
    if fixed:
        lines.append('已恢复 %d 项：%s' % (len(fixed), '、'.join(k.split('|')[1] for k in fixed[:6])))
    if weekly:
        lines.insert(0, '▍技能周报 %s：%d 个技能，自检 %d（失败 %d，未覆盖 %d），lint 硬错 %d 提示 %d，退休候选 %d' % (
            time.strftime('%m-%d'), cur['total'], cur['selftest_ran'], cur['selftest_failed'],
            cur['uncovered'], cur['lint_errors'], cur['lint_warnings'], cur['retire_candidates']))

    msg = chr(10).join(lines).strip()
    print(cur['ts'], '| total=%d lint_err=%d test_fail=%d retire=%d drift=%d new=%d' % (
        cur['total'], cur['lint_errors'], cur['selftest_failed'],
        cur['retire_candidates'], cur['drift'], len(new_issues)))
    if msg and not dry:
        if force or new_issues or weekly or fixed:
            run(['bash', NOTIFY, msg], timeout=120)
    elif msg and dry:
        print('DRY:')
        print(msg)
    return 0


def load_str(txt, default):
    try:
        return json.loads(txt)
    except Exception:
        return default


if __name__ == '__main__':
    sys.exit(main())
