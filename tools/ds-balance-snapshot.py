import json
p = '/home/j/.openclaw/workspace/state/model-econ/balances.json'
try:
    d = json.load(open(p))
    ds = (d.get('providers') or {}).get('deepseek') or {}
    av = ds.get('available')
    if isinstance(av, (int, float)):
        cur = ds.get('currency') or 'CNY'
        ts = d.get('updated_at') or ds.get('captured_at') or ''
        sym = '¥' if cur == 'CNY' else '$'
        print('%s%.2f (%s / %s)' % (sym, av, cur, ts))
except Exception:
    pass
