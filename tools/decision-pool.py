#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decision-pool.py — 决策组议案与裁决账本（2026-11-12）

用途：登记议案、记录各席票、按档位算裁决、渲染给主公看的一页。
不做模型调用：开会由在场 agent 用 sessions_spawn 拉各席模型，本工具只管规则与账。

用法：
  python3 tools/decision-pool.py new "标题" --tier L2 --body "提案正文" --rollback "回滚方式"
  python3 tools/decision-pool.py vote D-20261112-001 glm approve low "理由"
  python3 tools/decision-pool.py close D-20261112-001
  python3 tools/decision-pool.py list
  python3 tools/decision-pool.py show D-20261112-001
"""
import json, os, sys, time

WS = '/home/j/.openclaw/workspace'
DIR = os.path.join(WS, 'state', 'decisions')
LEDGER = os.path.join(DIR, 'ledger.jsonl')
POOL = os.path.join(DIR, 'pool.json')

def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')

def load_pool():
    with open(POOL, encoding='utf-8') as f:
        return json.load(f)

def load_all():
    items = []
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    return items

def save_all(items):
    tmp = LEDGER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    os.replace(tmp, LEDGER)

def find(items, did):
    for it in items:
        if it['id'] == did:
            return it
    return None

def cmd_new(args):
    title = args[0]
    tier = 'L2'; body = ''; rollback = ''; proposer = 'main'; facts = ''
    i = 1
    while i < len(args):
        if args[i] == '--tier':
            tier = args[i+1]; i += 2
        elif args[i] == '--body':
            body = args[i+1]; i += 2
        elif args[i] == '--rollback':
            rollback = args[i+1]; i += 2
        elif args[i] == '--proposer':
            proposer = args[i+1]; i += 2
        elif args[i] == '--facts':
            facts = args[i+1]; i += 2
        else:
            i += 1
    items = load_all()
    seq = len([x for x in items if x.get('date') == time.strftime('%Y%m%d')]) + 1
    did = 'D-%s-%03d' % (time.strftime('%Y%m%d'), seq)
    it = {'id': did, 'title': title, 'tier': tier, 'proposer': proposer,
          'body': body, 'rollback': rollback, 'facts_check': facts,
          'date': time.strftime('%Y%m%d'),
          'created': now(), 'votes': [], 'outcome': None, 'closed_at': None}
    if tier not in ('L1', 'L2', 'L3'):
        print('档位只能是 L1/L2/L3'); return 2
    if tier != 'L1' and not facts.strip():
        print('拒绝立议案：L2/L3 必须带 --facts（写清验过什么、用什么命令验的）')
        print('  原因：2026-11-12 首案因事实错误白烧三席调用（M-20261112-001）')
        return 3
    items.append(it)
    save_all(items)
    print(did)
    return 0

def cmd_vote(args):
    did, seat, verdict, risk = args[0], args[1], args[2], args[3]
    rest = args[4:]
    kill = ''
    reason_parts = []
    i = 0
    while i < len(rest):
        if rest[i] == '--kill':
            kill = rest[i+1]; i += 2
        else:
            reason_parts.append(rest[i]); i += 1
    reason = ' '.join(reason_parts)
    if verdict not in ('approve', 'reject', 'conditional'):
        print('票只能 approve/reject/conditional'); return 2
    items = load_all()
    it = find(items, did)
    if not it:
        print('无此议案'); return 2
    if it['outcome']:
        print('已结案，不能再投票（如需改判请新建议案）'); return 3
    if seat == it['proposer']:
        print('提案席回避，不能给自己投票'); return 3
    if it['tier'] == 'L3' and not kill:
        print('L3 议案必须给 kill criteria：--kill "出现什么情况就推翻本决定"'); return 3
    it['votes'] = [v for v in it['votes'] if v['seat'] != seat]
    it['votes'].append({'seat': seat, 'verdict': verdict, 'risk': risk,
                        'reason': reason, 'kill': kill, 'at': now()})
    save_all(items)
    print('%s <- %s %s' % (did, seat, verdict))
    return 0

def cmd_close(args):
    did = args[0]
    items = load_all()
    it = find(items, did)
    if not it:
        print('无此议案'); return 2
    pool = load_pool()
    tier = it['tier']
    votes = it['votes']
    appr = [v for v in votes if v['verdict'] == 'approve']
    cond = [v for v in votes if v['verdict'] == 'conditional']
    rej = [v for v in votes if v['verdict'] == 'reject']
    need = pool['tiers'][tier]['reviewers']
    total = len(votes)

    if tier == 'L1':
        outcome = 'pass_l1'
        note = 'L1 不入会，直接执行并报备'
    else:
        if total < need:
            print('票数不足：%d/%d，不能结案' % (total, need)); return 3
        yes = len(appr) + len(cond)
        quorum = (2/3) if tier == 'L2' else (3/4)
        if yes / total >= quorum:
            outcome = 'approved' if not cond else 'approved_with_conditions'
        elif yes / total > 0.5:
            outcome = 'needs_owner'
        else:
            outcome = 'rejected'
        if len(appr) == len(rej) and len(appr) > 0:
            outcome = 'tie_hold'
        note = '同意 %d/%d（含条件 %d），否决 %d' % (yes, total, len(cond), len(rej))

    if tier == 'L3' and outcome in ('approved', 'approved_with_conditions'):
        note += '；L3 仍需主公明示放行'

    it['outcome'] = outcome
    it['closed_at'] = now()
    it['note'] = note
    save_all(items)
    print('%s => %s（%s）' % (did, outcome, note))
    return 0

def cmd_list(args):
    items = load_all()
    if not items:
        print('（空）'); return 0
    for it in items[-30:]:
        print('%s [%s] %-8s %s' % (it['id'], it['tier'],
              (it['outcome'] or 'open'), it['title']))
    return 0

def cmd_show(args):
    items = load_all()
    it = find(items, args[0])
    if not it:
        print('无此议案'); return 2
    print('# %s  %s' % (it['id'], it['title']))
    print('档位 %s｜提案 %s｜创建 %s' % (it['tier'], it['proposer'], it['created']))
    if it.get('body'):
        print('正文：' + it['body'])
    if it.get('rollback'):
        print('回滚：' + it['rollback'])
    print('票：')
    for v in it['votes']:
        line = '  - %-8s %-12s risk=%-6s %s' % (v['seat'], v['verdict'], v['risk'], v['reason'])
        print(line)
        if v.get('kill'):
            print('      kill: ' + v['kill'])
    print('裁决：%s %s' % (it['outcome'] or '（未结）', it.get('note') or ''))
    return 0

def cmd_void(args):
    did = args[0]
    reason = args[1] if len(args) > 1 else ''
    items = load_all()
    it = find(items, did)
    if not it:
        print('无此议案'); return 2
    it['outcome'] = 'voided'
    it['closed_at'] = now()
    it['note'] = '作废：' + reason
    save_all(items)
    print('%s => voided' % did)
    return 0


POLICY = """议会开会政策（2026-11-12）
必开 L3：不可逆/删数据/改权限/改密钥/动暴露面 · 动钱 · 对外发布 · 全局配置(cron/模型链/备份/防火墙) · 返工两次 · 自报盲区
开   L2：跨机器跨盘批量操作 · 多管家排工变更 · 新机制首上线 · 改规则文档 · 任何删文件清单
不开 L1：可撤销单机小改 · 纯查询 · 已批同类照办 · 紧急止血（先修后补议案）
护栏：L3 每天≤3次 · 同议题24h不重开 · 必带 facts 与 kill criteria · 裁决≠放行，删除/密钥/权限/钱/外发仍需主公点头 · 平票维持现状
"""


def cmd_policy(args):
    print(POLICY.strip())
    return 0

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    cmd, a = sys.argv[1], sys.argv[2:]
    return {'new': cmd_new, 'vote': cmd_vote, 'close': cmd_close,
            'list': cmd_list, 'show': cmd_show, 'void': cmd_void, 'policy': cmd_policy}.get(cmd, lambda x: print('未知命令') or 1)(a)

if __name__ == '__main__':
    sys.exit(main())
