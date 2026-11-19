#!/usr/bin/env python3
# model-pool-model.py v1.0 (2026-11-18) —— 模型池「流量加权」模型与 45% 告警
# 为什么有它：现有 model-compliance-check.py 只按「管家个数」算集中度（39%），
# 但真实调用与花费 91.5% 都在 deepseek 一家。按个数算会给出假绿。
# 本工具从 state/usage-meter/ledger.jsonl 读真实用量，按 calls / cost 算份额，
# 再叠加 cron 级 model/fallback 引用，给出一张能看的池结构表。
# 用法:
#   python3 tools/model-pool-model.py               # 表格
#   python3 tools/model-pool-model.py --days 14
#   python3 tools/model-pool-model.py --json
#   python3 tools/model-pool-model.py --notify      # 仅越线时推飞书（供定时器用）
# 退出码: 0 正常 / 2 有越线
import json, os, sys, subprocess, collections, datetime

WS = '/home/j/.openclaw/workspace'
LEDGER = WS + '/state/usage-meter/ledger.jsonl'
LIMIT = 0.45
VENDOR_KEYS = [('deepseek', 'deepseek'), ('qianwen', 'qianwen'), ('qwen', 'qianwen'),
               ('glm', 'zai'), ('zai', 'zai'), ('minimax', 'minimax'),
               ('kimi', 'kimi'), ('ollama', 'ollama'), ('gpt-oss', 'ollama')]

def vendor_of(model):
    m = (model or '').lower()
    for k, v in VENDOR_KEYS:
        if k in m:
            return v
    if 'k3' in m:
        return 'kimi'
    if m in ('', 'command', 'automation-result'):
        return 'other'
    return m

def usage(days):
    cut = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    calls = collections.Counter(); cost = collections.Counter(); agent_cost = collections.Counter()
    if not os.path.exists(LEDGER):
        return calls, cost, agent_cost
    with open(LEDGER) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if (r.get('ts') or '') < cut:
                continue
            v = vendor_of(r.get('model'))
            calls[v] += 1
            cost[v] += float(r.get('cost_list') or 0)
            agent_cost[(r.get('agent') or '?', v)] += float(r.get('cost_list') or 0)
    return calls, cost, agent_cost

def agents():
    try:
        cfg = json.load(open('/home/j/.openclaw/openclaw.json'))
        ents = cfg['agents']['entries']
        return {k: (v.get('model') or {}).get('primary') for k, v in ents.items()}
    except Exception:
        return {}

def cron_jobs():
    try:
        exe = '/home/j/.npm-global/bin/openclaw'
        if not os.path.exists(exe):
            exe = 'openclaw'
        env = dict(os.environ)
        env['PATH'] = '/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:' + env.get('PATH', '')
        out = subprocess.run([exe, 'cron', 'list', '--json'], capture_output=True, text=True, timeout=90, env=env).stdout
        d = json.loads(out)
        jobs = d if isinstance(d, list) else d.get('jobs', d)
        return [j for j in jobs if j.get('enabled')]
    except Exception:
        return []

def main():
    days = 7
    as_json = '--json' in sys.argv
    notify = '--notify' in sys.argv
    if '--days' in sys.argv:
        try:
            days = int(sys.argv[sys.argv.index('--days') + 1])
        except Exception:
            pass
    calls, cost, agent_cost = usage(days)
    amap = agents()
    total_calls = sum(calls.values()) or 1
    total_cost = sum(cost.values()) or 1

    a_share = collections.Counter(vendor_of(m) for m in amap.values())
    total_agents = sum(a_share.values()) or 1

    # cron 引用面：primary 与 fallback 分别计
    prim = collections.Counter(); fb = collections.Counter()
    for j in cron_jobs():
        p = j.get('payload') or {}
        if p.get('kind') != 'agentTurn':
            continue
        prim[vendor_of(p.get('model') or 'deepseek/deepseek-flash')] += 1
        for x in p.get('fallbacks') or []:
            fb[vendor_of(x)] += 1

    vendors = [v for v in sorted(set(list(calls) + list(cost) + list(a_share) + list(prim)), key=lambda v: -cost.get(v, 0)) if v != 'other']
    rows = []
    breach = []
    for v in vendors:
        c_share = calls.get(v, 0) / total_calls
        k_share = cost.get(v, 0) / total_cost
        g_share = a_share.get(v, 0) / total_agents
        rows.append(dict(vendor=v, agents=a_share.get(v, 0), agent_share=round(g_share, 4),
                         calls=calls.get(v, 0), call_share=round(c_share, 4),
                         cost=round(cost.get(v, 0), 3), cost_share=round(k_share, 4),
                         cron_primary=prim.get(v, 0), cron_fallback=fb.get(v, 0)))
        if c_share > LIMIT:
            breach.append(('calls', v, c_share))
        elif g_share > LIMIT:
            breach.append(('agents', v, g_share))

    top_agents = [(a, round(c, 3)) for (a, v), c in agent_cost.most_common(5)]
    result = dict(days=days, limit=LIMIT, total_calls=total_calls, total_cost=round(total_cost, 3),
                  vendors=rows, breaches=[dict(basis=b, vendor=v, share=round(s, 4)) for b, v, s in breach],
                  top_agents=top_agents)

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print('【模型池流量加权 · 近 %d 天】调用 %d 次 / list 估算 $%.2f（上限 %.0f%%）'
              % (days, total_calls, total_cost, LIMIT * 100))
        print('%-9s %6s %7s %8s %8s %8s %7s %6s' % ('厂', '管家', '占比', '调用', '调用占比', '花费$', '花费占比', 'cron主'))
        for r in rows:
            print('%-9s %6d %6.0f%% %8d %7.0f%% %8.2f %7.0f%% %6d'
                  % (r['vendor'], r['agents'], 100 * r['agent_share'], r['calls'],
                     100 * r['call_share'], r['cost'], 100 * r['cost_share'], r['cron_primary']))
        print('越线：', ('无' if not breach else '；'.join('%s=%s %.0f%%' % (v, b, 100 * s) for b, v, s in breach)))
        print('花费前 5 管家：', '，'.join('%s $%.2f' % (a, c) for a, c in top_agents))

    try:
        os.makedirs(WS + '/state/model-econ', exist_ok=True)
        with open(WS + '/state/model-econ/pool-latest.json', 'w') as f:
            json.dump(dict(result, generated_at=datetime.datetime.now().isoformat(timespec='seconds')), f, ensure_ascii=False, indent=1)
    except Exception as e:
        print('snapshot failed:', e)

    if breach and notify:
        txt = '【模型池越线】%s 近 %d 天：%s；上限 %.0f%%。\n处置：python3 tools/model-pool-model.py 看明细'
        msg = txt % ('、'.join(sorted(set(v for _, v, _ in breach))), days,
                     '、'.join('%s %s %.0f%%' % (v, b, 100 * s) for b, v, s in breach), LIMIT * 100)
        try:
            subprocess.run(['bash', WS + '/tools/notify.sh', '--digest', msg], timeout=90)
        except Exception as e:
            print('notify failed:', e)
    return 2 if breach else 0

if __name__ == '__main__':
    sys.exit(main())
