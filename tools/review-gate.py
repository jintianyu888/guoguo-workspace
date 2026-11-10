#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''review-gate.py — 评审池准入门槛（主公 2026-11-07 21:04 批准）

规则（只看有分辨力的分项，不看总分）：
  1. 幻觉诱导题均分 < 0.60 → 禁入评审池
  2. 空输出率 > 5% → 未加空响应兜底前不进评审池（可做兜底）
  3. 总分仅作参考，不作为准入依据（本次 8 模型总分 0.79–0.96，中位数全 1.00，已饱和）
输出：state/model-warden/review-gate.json（allowed / blocked / 依据）
'''

import glob, json, os, statistics as st

WS = '/home/j/.openclaw/workspace'
MWS = '/home/j/.openclaw/workspace-model'
OUT = os.path.join(WS, 'state', 'model-warden', 'review-gate.json')
TH_HALLU = 0.60
TH_EMPTY = 0.05


def main():
    import re
    fs = sorted(p for p in glob.glob(os.path.join(MWS, 'state', 'model-warden', 'bench10-*.jsonl'))
                if re.search(r'bench10-\d{8}\.jsonl$', p))
    if not fs:
        print('无 bench10 数据')
        return 1
    f = fs[-1]
    rows = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
    by = {}
    for r in rows:
        by.setdefault(r['model'], []).append(r)
    allowed, blocked = [], []
    for m, rs in sorted(by.items()):
        ok = [x for x in rs if x.get('text', '').strip()]
        h = [x['score'] for x in ok if x.get('kind') == '幻觉诱导']
        hallu = round(st.mean(h), 2) if h else None
        empty_rate = round((len(rs) - len(ok)) / len(rs), 3) if rs else 1
        total = round(st.mean([x['score'] for x in ok]) * 10, 2) if ok else 0
        why = []
        if hallu is not None and hallu < TH_HALLU:
            why.append('幻觉诱导 %.2f < %.2f' % (hallu, TH_HALLU))
        if empty_rate > TH_EMPTY:
            why.append('空输出率 %.0f%% > %.0f%%' % (empty_rate * 100, TH_EMPTY * 100))
        rec = {'model': m, 'hallucination': hallu, 'empty_rate': empty_rate,
               'total_score': total, 'n': len(rs), 'evidence': os.path.relpath(f, WS)}
        if why:
            rec['reason'] = '；'.join(why)
            blocked.append(rec)
        else:
            allowed.append(rec)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'generated_at': os.popen('date "+%F %T"').read().strip(),
               'rule': {'hallucination_min': TH_HALLU, 'empty_rate_max': TH_EMPTY,
                        'note': '总分不作准入依据；空输出可用重试兜底后申请例外'},
               'allowed': allowed, 'blocked': blocked},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('证据:', os.path.relpath(f, WS))
    print('通过 %d / 拦截 %d' % (len(allowed), len(blocked)))
    for r in blocked:
        print('  ✗ %-32s %s' % (r['model'], r['reason']))
    for r in allowed:
        print('  ✓ %-32s 幻觉 %s 空 %s%% 总分 %s' % (r['model'], r['hallucination'], int(r['empty_rate'] * 100), r['total_score']))
    print('→', OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
