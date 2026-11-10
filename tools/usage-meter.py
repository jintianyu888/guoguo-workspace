#!/usr/bin/env python3
# usage-meter.py — 本地 Token/费用计数器（2026-10-23 主公令）
# 数据源：各管家 agent 的 openclaw-agent.sqlite（OpenClaw 本来就记录每次调用的用量）
# 特性：纯本地读文件，零 API 调用、零 token；增量采集，10 分钟一跑
#
# 输出：
#   state/usage-meter/ledger.jsonl   每次模型调用一行（时间/管家/模型/各类token/费用）
#   state/usage-meter/daily.csv      按天×模型汇总
#   state/usage-meter/hourly.csv     按小时×模型汇总
#
# 用法：
#   usage-meter.py collect        # 增量采集（给定时任务用）
#   usage-meter.py report [天数]  # 汇总打印，默认 7 天
import sqlite3, json, os, sys, glob
from collections import defaultdict
from datetime import datetime, timezone, timedelta

W   = '/home/j/.openclaw/workspace'
OUT = f'{W}/state/usage-meter'
STATE_PATH = f'{OUT}/meter-state.json'
TZ  = timezone(timedelta(hours=8))

# 订阅包月内的模型：边际成本=0（list price 照记，marginal 记 0）
# 注意：kimi-k3 走按量 API 时是计费的，不在此列；订阅端点的模型 ID 是 kimi-for-coding / k3 / k3-256k
SUB_EXACT = {'k3', 'k3-256k', 'kimi-for-coding', 'kimi-for-coding-highspeed', 'minimax-m-plan'}
SUB_PREFIX = ('glm-',)

def is_subscribed(model):
    m = (model or '').lower()
    return m in SUB_EXACT or any(m.startswith(p) for p in SUB_PREFIX)

def now_ms(): return int(datetime.now(TZ).timestamp()*1000)

def load_state():
    try:
        with open(STATE_PATH) as f: return json.load(f)
    except Exception: return {}

def save_state(s):
    tmp = STATE_PATH+'.tmp'
    with open(tmp,'w') as f: json.dump(s,f)
    os.replace(tmp, STATE_PATH)

def collect():
    os.makedirs(OUT, exist_ok=True)
    state = load_state()
    ledger = open(f'{OUT}/ledger.jsonl','a', buffering=1)
    n_new = 0
    for db in sorted(glob.glob('/home/j/.openclaw/agents/*/agent/openclaw-agent.sqlite')):
        agent = db.split('/agents/')[1].split('/')[0]
        wm_key = f'wm:{db}'
        wm = int(state.get(wm_key, 0))
        new_wm = wm
        try:
            c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
            # created_at 单调递增（毫秒）；只取纯文本事件里 role=assistant 的用量
            q = c.execute(
                "SELECT created_at, event_json FROM transcript_events "
                "WHERE created_at > ? AND event_json IS NOT NULL ORDER BY created_at", (wm,))
            for ts, ej in q:
                new_wm = max(new_wm, ts)
                try: j = json.loads(ej)
                except Exception: continue
                msg = j.get('message') or {}
                if msg.get('role') == 'user':
                    _dk = 'u:' + datetime.fromtimestamp(ts/1000, TZ).strftime('%F')
                    state[_dk] = int(state.get(_dk, 0)) + 1
                if msg.get('role') != 'assistant': continue
                u = msg.get('usage') or {}
                if not u: continue
                model = msg.get('model') or 'unknown'
                if model == 'delivery-mirror': continue
                cost = u.get('cost') or {}
                rec = {
                    'ts': datetime.fromtimestamp(ts/1000, TZ).strftime('%F %T'),
                    'agent': agent,
                    'model': model,
                    'input': u.get('input',0),
                    'output': u.get('output',0),
                    'cacheRead': u.get('cacheRead',0),
                    'cacheWrite': u.get('cacheWrite',0),
                    'reasoning': u.get('reasoningTokens',0),
                    'cost_list': round(float(cost.get('total',0) or 0),6),
                    'cost_marginal': 0.0 if is_subscribed(model) else round(float(cost.get('total',0) or 0),6),
                }
                ledger.write(json.dumps(rec, ensure_ascii=False)+'\n')
                n_new += 1
            c.close()
        except Exception as e:
            print(f'WARN {agent}: {e}', file=sys.stderr)
            continue
        state[wm_key] = new_wm
    ledger.close()
    save_state(state)
    turns = {k[2:]: int(v) for k, v in state.items() if k.startswith('u:')}
    try:
        with open(f'{OUT}/user-turns.json', 'w') as f:
            json.dump(dict(sorted(turns.items())[-30:]), f, ensure_ascii=False)
    except Exception as e:
        print('WARN user-turns:', e, file=sys.stderr)
    rebuild_csv()
    return n_new

def iter_ledger():
    try:
        with open(f'{OUT}/ledger.jsonl') as f:
            for line in f:
                try: yield json.loads(line)
                except Exception: continue
    except FileNotFoundError: return

def rebuild_csv():
    daily = defaultdict(lambda: [0,0,0,0,0,0.0,0.0,0])   # in,out,cr,cw,reason,cost_list,cost_marginal,calls
    hourly = defaultdict(lambda: [0,0,0,0,0,0.0,0.0,0])
    for r in iter_ledger():
        if r.get('model') == 'delivery-mirror': continue
        d = r['ts'][:10]; h = r['ts'][:13]; m = r['model']
        for key, agg in (( (d,m), daily ), ( (h,m), hourly )):
            a = agg[key]
            a[0]+=r['input']; a[1]+=r['output']; a[2]+=r['cacheRead']; a[3]+=r['cacheWrite']
            a[4]+=r['reasoning']; a[5]+=r['cost_list']; a[6]+=r['cost_marginal']; a[7]+=1
    def dump(path, agg, dim):
        with open(path,'w',newline='') as f:
            f.write(f'{dim},model,input,output,cacheRead,cacheWrite,reasoning,cost_list,cost_marginal,calls\n')
            for (k,m),a in sorted(agg.items()):
                f.write(f'{k},{m},{a[0]},{a[1]},{a[2]},{a[3]},{a[4]},{a[5]:.4f},{a[6]:.4f},{a[7]}\n')
    dump(f'{OUT}/daily.csv', daily, 'date')
    dump(f'{OUT}/hourly.csv', hourly, 'hour')

def report(days=7):
    since = (datetime.now(TZ)-timedelta(days=days)).strftime('%F')
    agg = defaultdict(lambda: [0,0,0,0,0,0.0,0.0,0])
    for r in iter_ledger():
        if r['ts'][:10] < since: continue
        a = agg[r['model']]
        a[0]+=r['input']; a[1]+=r['output']; a[2]+=r['cacheRead']; a[3]+=r['cacheWrite']
        a[4]+=r['reasoning']; a[5]+=r['cost_list']; a[6]+=r['cost_marginal']; a[7]+=1
    if not agg:
        print(f'最近 {days} 天暂无记录'); return
    print(f'最近 {days} 天（list price 估值 / marginal=订阅内按0计）：')
    print(f"{'模型':<28}{'调用':>6}{'输入K':>10}{'输出K':>10}{'缓存读M':>10}{'费用$':>10}{'边际$':>10}")
    tin=tout=tcr=tcl=tcm=tcalls=0
    for m,a in sorted(agg.items(), key=lambda kv:-kv[1][5]):
        print(f"{m:<28}{a[7]:>6}{a[0]/1000:>10.0f}{a[1]/1000:>10.0f}{a[2]/1e6:>10.1f}{a[5]:>10.3f}{a[6]:>10.3f}")
        tin+=a[0]; tout+=a[1]; tcr+=a[2]; tcl+=a[5]; tcm+=a[6]; tcalls+=a[7]
    print('-'*84)
    print(f"{'合计':<28}{tcalls:>6}{tin/1000:>10.0f}{tout/1000:>10.0f}{tcr/1e6:>10.1f}{tcl:>10.3f}{tcm:>10.3f}")

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv)>1 else 'report'
    if cmd == 'collect':
        n = collect()
        print(f'usage-meter: +{n} 条新记录')
    elif cmd == 'report':
        d = int(sys.argv[2]) if len(sys.argv)>2 else 7
        report(d)
    else:
        print('用法: usage-meter.py {collect|report [天数]}'); sys.exit(2)
