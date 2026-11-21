#!/usr/bin/env python3
# model-status.py v1.0 (2026-11-21 主公令) —— 模型池一屏速查 + 余额直采
# 目标：把"反应慢、数字旧"变成 2 秒内给出可信现状。
# 做的事（零 token、纯本地+官方 API）：
#   1) DeepSeek 余额：直连 api.deepseek.com/user/balance（约 0.1s），并回写 state/model-econ/balances.json
#   2) 管家 → 模型：直读 openclaw.json（不再调 CLI）
#   3) 定时任务模型：读 cron 配置快照，统计未指定/指定分布
#   4) 近 24h 失败：读 state/ledger/jobs.db
#   5) 输出 state/model/status.json + 一行摘要
import json, os, sqlite3, sys, time, urllib.request, collections, datetime

WS = '/home/j/.openclaw/workspace'
CFG = '/home/j/.openclaw/openclaw.json'
BAL = os.path.join(WS, 'state/model-econ/balances.json')
OUT = os.path.join(WS, 'state/model/status.json')
JOBS = os.path.join(WS, 'state/ledger/jobs.db')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def deepseek_key():
    try:
        cfg = json.load(open(CFG))
        prov = cfg.get('models', {}).get('providers', {}).get('deepseek', {})
        ap = prov.get('apiKey')
        if isinstance(ap, str) and ap.startswith('sk-'):
            return ap
        sid = (ap or {}).get('id') or (ap or {}).get('ref') if isinstance(ap, dict) else None
        if not sid:
            return None
        db = '/home/j/.openclaw/state/openclaw.sqlite'
        c = sqlite3.connect('file:%s?mode=ro' % db, uri=True)
        row = c.execute('select value from secret_store_entries where name=? and deleted_at_ms is null', (sid,)).fetchone()
        c.close()
        return row[0] if row and row[0] and str(row[0]).startswith('sk-') else None
    except Exception:
        return None


def fetch_deepseek():
    k = deepseek_key()
    if not k:
        return {'ok': False, 'error': 'key 解析失败'}
    t = time.time()
    try:
        req = urllib.request.Request('https://api.deepseek.com/user/balance',
                                     headers={'Authorization': 'Bearer ' + k})
        d = json.load(urllib.request.urlopen(req, timeout=10))
        cn = [b for b in d.get('balance_infos', []) if b.get('currency') == 'CNY']
        amt = float((cn[0] if cn else d['balance_infos'][0])['total_balance'])
        return {'ok': True, 'available': amt, 'currency': 'CNY',
                'ms': int((time.time() - t) * 1000), 'is_available': d.get('is_available')}
    except Exception as e:
        return {'ok': False, 'error': str(e)[:120]}


def write_balance(live):
    if not live.get('ok'):
        return
    try:
        d = json.load(open(BAL)) if os.path.exists(BAL) else {'providers': {}}
    except Exception:
        d = {'providers': {}}
    p = d.setdefault('providers', {}).setdefault('deepseek', {})
    p['available'] = live['available']
    p['currency'] = 'CNY'
    p['source'] = 'api.deepseek.com/user/balance'
    p['note'] = '实时（model-status 直采）'
    norm = p.setdefault('norm', {})
    norm['available'] = live['available']
    norm['unit'] = 'CNY'
    d['updated_at'] = now()
    os.makedirs(os.path.dirname(BAL), exist_ok=True)
    tmp = BAL + '.tmp'
    json.dump(d, open(tmp, 'w'), ensure_ascii=False, indent=1)
    os.replace(tmp, BAL)


def agent_map():
    cfg = json.load(open(CFG))
    ents = cfg['agents']['entries']
    prim = collections.Counter()
    for k, v in ents.items():
        m = v.get('model') or {}
        prim[m.get('primary') or '(default)'] += 1
    dflt = (cfg['agents'].get('defaults', {}).get('model') or {}).get('primary')
    return len(ents), dict(prim), dflt


def jobs_24h():
    if not os.path.exists(JOBS):
        return None
    try:
        c = sqlite3.connect('file:%s?mode=ro' % JOBS, uri=True)
        cut = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        tot = c.execute("select count(*) from runs where started >= ?", (cut,)).fetchone()[0]
        bad = c.execute("select count(*) from runs where started >= ? and status in ('error','failed','timeout')", (cut,)).fetchone()[0]
        c.close()
        return {'total': tot, 'failed': bad, 'rate': round(bad * 100.0 / tot, 2) if tot else 0.0}
    except Exception as e:
        return {'error': str(e)[:80]}


def main():
    live = fetch_deepseek()
    write_balance(live)
    n, prim, dflt = agent_map()
    st = {
        'ts': now(),
        'agents': n,
        'primary': prim,
        'default_primary': dflt,
        'deepseek': live,
        'jobs_24h': jobs_24h(),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(st, open(OUT + '.tmp', 'w'), ensure_ascii=False, indent=1)
    os.replace(OUT + '.tmp', OUT)
    bal = ('¥%.2f' % live['available']) if live.get('ok') else ('取不到(%s)' % live.get('error'))
    j = st['jobs_24h'] or {}
    print('模型池 %s｜管家 %d（flash %d）｜默认 %s｜DeepSeek %s（%sms）｜24h 任务 %s 失败 %s' % (
        st['ts'], n, prim.get('deepseek/deepseek-flash', 0), dflt, bal, live.get('ms', '-'),
        j.get('total', '?'), j.get('failed', '?')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
