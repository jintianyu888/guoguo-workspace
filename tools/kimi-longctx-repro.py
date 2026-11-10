#!/usr/bin/env python3
# kimi-longctx-repro.py — 复现 kimi-k3 长提示空回：3 档长度 + v4-pro 对照
# 用法: python3 tools/kimi-longctx-repro.py [model]
# 输出: state/eval/kimi-longctx-<ts>.json + 终端摘要
import json, os, subprocess, sys, time, datetime
WS = '/home/j/.openclaw/workspace'
SEED = open(WS + '/tools/backup-retain.sh').read()
Q = '用一句话回答：这段材料里定义的锁文件路径是什么？只输出路径本身。' + chr(10) + chr(10)
SIZES = [3000, 12000, 40000]
def build(n):
    body = (SEED * (n // max(len(SEED), 1) + 2))[:n]
    return Q + body
def call(m, p, to=180):
    t = time.time()
    try:
        r = subprocess.run(['openclaw','infer','model','run','--agent','main','--gateway','--model',m,'--prompt',p], capture_output=True, text=True, timeout=to)
        out = r.stdout.split('outputs: 1', 1)[-1].strip()
        return {'rc': r.returncode, 'bytes': len(out), 'secs': round(time.time()-t, 1), 'out': out}
    except subprocess.TimeoutExpired:
        return {'rc': -1, 'bytes': 0, 'secs': round(time.time()-t, 1), 'out': 'TIMEOUT'}
def main():
    m = sys.argv[1] if len(sys.argv) > 1 else 'moonshot/kimi-k3'
    rows = []
    for n in SIZES:
        r = call(m, build(n))
        hit = 'backup-retain.lock' in r['out']
        r.update(model=m, prompt_chars=n, marker_hit=hit)
        rows.append(r)
        print('%-22s %6d字 rc=%-3s %6.1fs %5dB 命中=%-5s %r' % (m, n, r['rc'], r['secs'], r['bytes'], hit, r['out'][:60]), flush=True)
    c = call('deepseek/deepseek-v4-pro', build(SIZES[-1]))
    c.update(model='deepseek/deepseek-v4-pro', prompt_chars=SIZES[-1], marker_hit='backup-retain.lock' in c['out'], control=True)
    rows.append(c)
    print('%-22s %6d字 rc=%-3s %6.1fs %5dB 命中=%-5s %r' % ('v4-pro(对照)', SIZES[-1], c['rc'], c['secs'], c['bytes'], c['marker_hit'], c['out'][:60]), flush=True)
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    p = WS + '/state/eval/kimi-longctx-' + ts + '.json'
    json.dump({'ts': ts, 'rows': rows}, open(p, 'w'), ensure_ascii=False, indent=1)
    print('SAVED ' + p)
main()