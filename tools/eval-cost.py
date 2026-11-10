#!/usr/bin/env python3
"""eval-cost.py —— 评测成本列：维护价格表，按 token 用量算每千 token 成本

用法:
  eval-cost.py --add-cols          给 state/eval/eval.db runs 表补 tokens_in/tokens_out 列
  eval-cost.py --report [--top N]  打印各模型分数/耗时/成本（无 token 数据写「未采集」）
  eval-cost.py --price key=in:out  维护价格表（单位 ¥/百万 token），零不改既有数据
"""
import os, sys, json, sqlite3, argparse

W = '/home/j/.openclaw/workspace'
DB = os.path.join(W, 'state/eval/eval.db')
PRICES = os.path.join(W, 'state/eval/prices.json')

def load_prices():
    try: return json.load(open(PRICES, encoding='utf-8'))
    except Exception: return {}

def save_prices(p):
    os.makedirs(os.path.dirname(PRICES), exist_ok=True)
    json.dump(p, open(PRICES, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def add_cols():
    c = sqlite3.connect(DB)
    cols = [d[1] for d in c.execute('pragma table_info(runs)')]
    for name, typ in (('tokens_in', 'INTEGER'), ('tokens_out', 'INTEGER')):
        if name not in cols:
            c.execute('ALTER TABLE runs ADD COLUMN %s %s' % (name, typ))
            print('加列', name)
    c.commit()
    print('列:', [d[1] for d in c.execute('pragma table_info(runs)')])

def cost_of(prices, model, ti, to):
    p = None
    for k, v in prices.items():
        if k == model or (k and k in (model or '')):
            p = v; break
    if not p or ti is None or to is None: return None
    return (ti * p.get('in', 0) + to * p.get('out', 0)) / 1e6

def report(top):
    prices = load_prices()
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = c.execute('select provider, model, score, latency_s, tokens_in, tokens_out, cost_cny from runs order by ts desc limit 200').fetchall()
    print('%-22s %-28s %6s %7s %10s %10s' % ('provider','model','score','耗时s','¥/千tok','成本¥'))
    seen = set()
    n = 0
    for r in rows:
        key = (r['provider'], r['model'])
        if key in seen: continue
        seen.add(key)
        ti, to = r['tokens_in'], r['tokens_out']
        cst = r['cost_cny'] or cost_of(prices, r['model'], ti, to)
        if cst and (ti or to):
            per1k = cst / max(1.0, ((ti or 0) + (to or 0)) / 1000.0)
            per1k_s = '%.4f' % per1k
        else:
            per1k_s = '未采集'
        cost_s = '%.4f' % cst if cst else '未采集'
        print('%-22s %-28s %6s %7s %10s %10s' % (r['provider'], (r['model'] or '')[:28], r['score'], r['latency_s'], per1k_s, cost_s))
        n += 1
        if n >= top: break

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--add-cols', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--price', nargs='*')
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args()
    if a.add_cols: add_cols(); return 0
    if a.price:
        p = load_prices()
        for kv in a.price:
            k, v = kv.split('=', 1); i, o = v.split(':')
            p[k] = {'in': float(i), 'out': float(o)}
        save_prices(p); print('价格表已更新:', PRICES); return 0
    report(a.top); return 0

if __name__ == '__main__':
    sys.exit(main())
