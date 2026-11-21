#!/usr/bin/env python3
# model-footer.py v1.0 (2026-11-18 主公令) —— 回复页脚：本条回复用的模型 + 该厂余额/额度 + 数据刷新时间
# 目的：主公按每条回复监督模型池状态（谁在干活、谁快没额度、数据多旧）。
# 数据源（零 API 调用、纯本地读）：
#   state/model-econ/balances.json  余额/额度（抓页 + DeepSeek 官方 API，updated_at 即刷新时间）
#   state/model-econ/quotas.json    套餐剩余（千问等）
# 用法:
#   python3 tools/model-footer.py deepseek/deepseek-flash
#   python3 tools/model-footer.py zai/glm-5.3
#   python3 tools/model-footer.py --all        # 各家一行，便于巡检
# 输出示例: ▍模型 deepseek/deepseek-flash｜DeepSeek 余额 ¥108.17｜刷新 20:06
import json, os, sys, datetime

E = '/home/j/.openclaw/workspace/state/model-econ'
BAL = os.path.join(E, 'balances.json')
QUO = os.path.join(E, 'quotas.json')


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def vendor_of(m):
    s = (m or '').lower()
    for k, v in [('deepseek', 'deepseek'), ('qwen', 'qianwen'), ('qianwen', 'qianwen'),
                 ('glm', 'zai'), ('zai', 'zai'), ('minimax', 'minimax'),
                 ('kimi', 'kimi'), ('k3', 'kimi'), ('ollama', 'ollama'), ('gpt-oss', 'ollama'),
                 ('gemma', 'free'), ('ernie', 'baidu'), ('nemotron', 'free'), ('free', 'free')]:
        if k in s:
            return v
    return 'unknown'


def age_note(stamp):
    """把 updated_at / captured_at 变成 '刷新 HH:MM'，过旧时标小时数。"""
    if not stamp:
        return '刷新时间未知'
    stamp = str(stamp).replace('T', ' ')[:16]
    try:
        t = datetime.datetime.strptime(stamp, '%Y-%m-%d %H:%M')
    except Exception:
        return '刷新 ' + stamp[11:16] if len(stamp) >= 16 else '刷新时间未知'
    mins = int((datetime.datetime.now() - t).total_seconds() // 60)
    if mins < 0:
        return '刷新 ' + t.strftime('%H:%M')
    if mins <= 90:
        return '刷新 ' + t.strftime('%H:%M')
    if mins <= 60 * 36:
        return '刷新 %s（%d 小时前）' % (t.strftime('%m-%d %H:%M'), mins // 60)
    return '刷新 %s（%d 天前，数据已旧）' % (t.strftime('%m-%d %H:%M'), mins // 1440)


def _cap(qp, norm, bal):
    """取刷新时间：优先 quotas 的 captured_at，其次 last_try_at，最后 balances 的 norm。"""
    for c in (qp.get('captured_at'), qp.get('last_try_at')):
        if c:
            return c
    c = norm.get('captured_at') or bal.get('updated_at')
    if isinstance(c, dict):
        return c.get('at')
    return c


def bal_line(v, bal, quo):
    prov = (bal.get('providers') or {}).get(v) or {}
    norm = prov.get('norm') or {}
    qp = (quo.get('providers') or {}).get(v) or {}
    hand = age_note(_cap(qp, norm, bal))

    if v == 'deepseek':
        # 2026-11-21：优先 balances.json 的实时值（model-status 直采），quotas 只作兜底
        av = norm.get('available')
        if av is None:
            av = qp.get('balance')
        hand = age_note(bal.get('updated_at'))
        if av is None:
            av = norm.get('available')
        cur = '¥' if (qp.get('currency') or norm.get('unit')) == 'CNY' else ''
        body = ('DeepSeek 余额 %s%s' % (cur, av)) if av is not None else 'DeepSeek 余额未采集'
        note = qp.get('note') if isinstance(qp.get('note'), str) and len(str(qp.get('note'))) < 40 else ''
        if note:
            body += '（%s）' % note
        return body + '｜' + hand

    if v == 'zai':
        h5 = qp.get('window_pct', (norm.get('h5_pct')))
        wk = qp.get('weekly_pct', (norm.get('week_pct')))
        return '智谱 Coding 已用 5h %s%% / 周 %s%%｜%s' % (h5, wk, hand)

    if v == 'minimax':
        h5 = qp.get('window_pct', norm.get('h5_pct'))
        wk = qp.get('weekly_pct', norm.get('week_pct'))
        exp = qp.get('plan_expire') or norm.get('plan_expire')
        body = 'M Plan 已用 5h %s%% / 周 %s%%' % (h5, wk)
        if exp:
            body += '（套餐 %s 到期）' % str(exp)[:10]
        return body + '｜' + hand

    if v == 'kimi':
        mo = qp.get('month_pct')
        if mo is None:
            mo = (norm.get('month') or {}).get('used')
        body = 'Kimi 月卡已用 %s%%' % mo if mo is not None else 'Kimi 额度未采集'
        if mo is not None and float(mo) >= 99:
            body = 'Kimi 额度耗尽（月卡 %s%%）' % mo
        exp = qp.get('plan_expire')
        if exp:
            body += '（套餐 %s 到期）' % str(exp)[:10]
        return body + '｜' + hand

    if v == 'qianwen':
        rem = qp.get('month_remaining_pct')
        used = qp.get('month_used_pct')
        exp = qp.get('plan_expire') or ''
        days = qp.get('days_left')
        body = '千问剩余 %s%%' % rem if rem is not None else '千问额度未采集'
        if used is not None:
            body += '（已用 %s%%）' % used
        if exp:
            body += '｜%s 到期' % str(exp)[:10]
        if days is not None:
            body += '（还剩 %s 天）' % days
        return body + '｜' + hand

    if v == 'ollama':
        return '本地 ollama（零成本）｜非云端，无余额'
    if v in ('free', 'baidu'):
        return '免费额度模型（无余额概念）｜—'
    return '该厂余额未采集｜—'


def line(model):
    v = vendor_of(model)
    bal = load(BAL); quo = load(QUO)
    return '▍模型 %s｜%s' % (model, bal_line(v, bal, quo))


def main():
    a = sys.argv[1:]
    if not a:
        print('用法: python3 tools/model-footer.py <provider/model>  |  --all')
        return 2
    if a[0] == '--all':
        for m in ['deepseek/deepseek-flash', 'zai/glm-5.3', 'minimax/MiniMax-M3.1-Flash-Preview',
                  'qianwen-token-plan/qwen3.8-flash', 'kimi-coding/kimi-for-coding', 'ollama/gpt-oss:20b']:
            print(line(m))
        return 0
    print(line(a[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
