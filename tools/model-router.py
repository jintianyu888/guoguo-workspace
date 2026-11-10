#!/usr/bin/env python3
"""model-router.py —— 路由池：按任务类型分派模型（静态路由表，本地零 token）

用: plan [--all]        列出每个 agentTurn 任务的类型判定 + 建议模型 + 现值
    apply --dry         只打印将要执行的 cron edit（不落地）
    apply --yes         真落（仅改「当前无 model 覆盖且判定高置信」的任务）
    table               打印路由表与档位说明
读: state/openclaw.sqlite(cron_jobs) + state/model-econ/balances.json
写: state/router/plan-YYYYMMDD.md（plan 输出留档）；改配置只走 openclaw cron edit
"""
import json, os, re, sys, sqlite3, datetime, subprocess

WS = '/home/j/.openclaw/workspace'
OCDB = '/home/j/.openclaw/state/openclaw.sqlite'
OUT = os.path.join(WS, 'state/router')

# 档位：模型 -> (档名, 计费, 备注)
TIERS = {
    'deepseek/deepseek-v4-pro':      ('强档', '现付', '推理强，贵；留给规划/决策'),
    'deepseek/deepseek-flash':       ('标准', '现付', '中文稳，日常主力'),
    'kimi-coding/k3-256k':           ('强档', '订阅', '长上下文审查用，11-22 到期'),
    'kimi-coding/kimi-for-coding':   ('强档', '订阅', '同族，质量略低但快'),
    'zai/glm-5.3-flash':             ('快档', '免费额度', '审查/提取够用，额度有限'),
    'zai/glm-5.3':                   ('标准', '免费额度', '比 flash 稳，也吃额度'),
    'qianwen-token-plan/qwen3.8-flash': ('便宜', '免费额度', '抽取/汇总首选'),
    'ollama/ornith-1.5:9b':          ('本地', '免费', '离线兜底，能力有限'),
}

# 任务类型 -> (建议主力, 兜底)
ROUTES = {
    'think':   ('deepseek/deepseek-v4-pro', ['kimi-coding/k3-256k', 'deepseek/deepseek-flash']),
    'review':  ('kimi-coding/k3-256k', ['zai/glm-5.3', 'deepseek/deepseek-flash']),
    'report':  ('deepseek/deepseek-flash', ['zai/glm-5.3-flash', 'qianwen-token-plan/qwen3.8-flash']),
    'extract': ('qianwen-token-plan/qwen3.8-flash', ['zai/glm-5.3-flash', 'ollama/ornith-1.5:9b']),
    'digest':  ('zai/glm-5.3-flash', ['qianwen-token-plan/qwen3.8-flash', 'ollama/ornith-1.5:9b']),
}

# 关键词 -> 类型（顺序即优先级）
RULES = [
    ('think',  ['规划', '决策', '拍板', '方案', '复盘', '周计划', '月结', '年结', '架构']),
    ('review', ['审查', '双审', '三审', '交叉验证', '评审', '体检', '督察', '盲区', '巡检']),
    ('extract',['抽取', '提取', '清洗', '统计', '核对', '比对', '清单', '归档', '整理']),
    ('digest', ['汇总', '摘要', '简报', '提醒', '候选', '统计表']),
    ('report', ['报告', '播报', '推送', '通报', '通知', '日结', '总结', '自审', '体检']),
]

def classify(name, desc=''):
    t = (name or '') + ' ' + (desc or '')
    for kind, kws in RULES:
        if any(k in t for k in kws):
            return kind, True
    return 'report', False   # 判不出就当普通报告档，低置信

def jobs():
    c = sqlite3.connect(OCDB)
    c.row_factory = sqlite3.Row
    rows = c.execute("select job_id,name,agent_id,payload_kind,job_json,enabled from cron_jobs").fetchall()
    out = []
    for r in rows:
        try:
            j = json.loads(r['job_json'])
        except Exception:
            j = {}
        out.append({
            'id': r['job_id'], 'name': r['name'], 'agent': r['agent_id'],
            'kind': r['payload_kind'], 'enabled': r['enabled'],
            'model': j.get('model') or (j.get('payload') or {}).get('model'),
            'fallbacks': j.get('fallbacks'),
        })
    return out

def balances():
    p = os.path.join(WS, 'state/model-econ/balances.json')
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return {}

def cmd_table():
    print('== 路由表 ==')
    for k in ('think', 'review', 'report', 'extract', 'digest'):
        m, fb = ROUTES[k]
        t = TIERS.get(m, ('?', '?', ''))
        print('%-8s %-34s %s / %s  兜底: %s' % (k, m, t[0], t[1], ','.join(fb)))
    print('\n== 档位 ==')
    for m, (tier, pay, note) in TIERS.items():
        print('%-34s %-4s %-6s %s' % (m, tier, pay, note))

def cmd_plan(show_all=False):
    rows = [j for j in jobs() if j['enabled'] and j['kind'] in ('agentTurn', 'heartbeat')]
    if not show_all:
        rows = [j for j in rows if not j['model']]
    plan = []
    for j in rows:
        kind, sure = classify(j['name'])
        want, fb = ROUTES[kind]
        cur = j['model'] or '(跟随 agent 默认)'
        act = '' if j['model'] == want else ('改' if sure else '待人工判')
        plan.append((j['id'], j['agent'], j['name'], kind, cur, want, act, sure))
    os.makedirs(OUT, exist_ok=True)
    day = datetime.datetime.now().strftime('%Y%m%d')
    p = os.path.join(OUT, 'plan-%s.md' % day)
    lines = ['# 路由池方案 · %s' % datetime.datetime.now().strftime('%F %T'),
             '范围: 启用中的 agentTurn/heartbeat %d 个；其中无 model 覆盖 %d 个' % (
                 len([j for j in jobs() if j['enabled'] and j['kind'] in ('agentTurn', 'heartbeat')]),
                 len([j for j in jobs() if j['enabled'] and j['kind'] in ('agentTurn', 'heartbeat') and not j['model']])),
             '']
    by_kind = {}
    for r in plan:
        by_kind[r[3]] = by_kind.get(r[3], 0) + 1
    lines.append('判定分布: ' + ', '.join('%s=%d' % (k, v) for k, v in sorted(by_kind.items())))
    lines.append('')
    for r in plan:
        lines.append('- [%s] %-26s %-6s 现:%s -> %s %s' % ((r[1] or '-')[:8], (r[2] or '')[:26], r[3], r[4], r[5], r[6]))
    open(p, 'w', encoding='utf-8').write('\n'.join(lines))
    for r in plan[:14]:
        print('[%s] %-24s %-7s %s -> %s %s' % ((r[1] or '-')[:8], (r[2] or '')[:24], r[3], (r[4] or '')[:26], r[5], r[6]))
    print('... 共 %d 条，明细 %s' % (len(plan), p))
    bal = balances()
    if bal:
        print('余额快照: ' + json.dumps({k: (v.get('balance') if isinstance(v, dict) else v) for k, v in list(bal.items())[:6]}, ensure_ascii=False))

def cmd_apply(dry=True):
    rows = [j for j in jobs() if j['enabled'] and j['kind'] in ('agentTurn', 'heartbeat') and not j['model']]
    todo = []
    for j in rows:
        kind, sure = classify(j['name'])
        if not sure:
            continue
        want, fb = ROUTES[kind]
        todo.append((j['id'], j['name'], want, fb))
    for jid, name, want, fb in todo:
        cmd = ['openclaw', 'cron', 'edit', jid, '--model', want, '--fallbacks', ','.join(fb)]
        if dry:
            print('DRY', want.split('/')[-1], '|', name[:26], '|', ','.join(fb))
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            print(('ok  ' if r.returncode == 0 else 'FAIL'), name[:24], want, (r.stderr or '')[:80])
    print('共 %d 条%s' % (len(todo), '（dry）' if dry else ''))

def main():
    a = sys.argv[1:]
    c = a[0] if a else 'plan'
    if c == 'table':
        return cmd_table()
    if c == 'plan':
        return cmd_plan('--all' in a)
    if c == 'apply':
        return cmd_apply(dry='--yes' not in a)
    print(__doc__)

if __name__ == '__main__':
    main()
