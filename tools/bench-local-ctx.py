#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tools/bench-local-ctx.py — 本地模型按指定窗口复测（自派工 #918）
# 用法: python3 tools/bench-local-ctx.py --ctx 32768
import json, time, urllib.request, argparse, datetime, os, sys

P = argparse.ArgumentParser()
P.add_argument('--endpoint', default=os.environ.get('B_ENDPOINT', 'http://192.168.1.107:11434'))
P.add_argument('--model', default=os.environ.get('BENCH_MODEL', 'mimo-v2.6:latest'))
P.add_argument('--ctx', type=int, default=32768)
P.add_argument('--label', default='local')
P.add_argument('--out', default='/home/j/.openclaw/workspace-model/state/model-warden/bench-local-%s.jsonl' % datetime.date.today().strftime('%Y%m%d'))
a = P.parse_args()

def post(path, body, timeout=900):
    req = urllib.request.Request(a.endpoint + path, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def ps():
    try:
        with urllib.request.urlopen(a.endpoint + '/api/ps', timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {'error': str(e)}

def gen(prompt, npred=128, keep='10m'):
    body = {'model': a.model, 'prompt': prompt, 'stream': False, 'think': False,
            'keep_alive': keep, 'options': {'num_ctx': a.ctx, 'num_predict': npred,
                                            'temperature': 0}}
    t0 = time.time()
    r = post('/api/generate', body)
    wall = time.time() - t0
    ev = (r.get('eval_count') or 0)
    evd = (r.get('eval_duration') or 0) / 1e9
    pe = (r.get('prompt_eval_count') or 0)
    ped = (r.get('prompt_eval_duration') or 0) / 1e9
    return {
        'wall_s': round(wall, 2),
        'load_s': round((r.get('load_duration') or 0) / 1e9, 2),
        'prompt_tokens': pe,
        'gen_tokens': ev,
        'gen_tps': round(ev / evd, 1) if evd > 0 else None,
        'prefill_tps': round(pe / ped, 1) if ped > 0 else None,
        'answer': (r.get('response') or '').strip(),
    }

rec = {'ts': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
       'label': a.label, 'model': a.model, 'ctx': a.ctx, 'endpoint': a.endpoint,
       'ps_before': ps()}

# 1) 预热（冷加载）
rec['warmup'] = gen('说一个字。', 2, '10m')
rec['ps_after_warmup'] = ps()

# 2) 速度：中文提示，取热态 128 token
rec['speed'] = gen('用中文写一段 120 字左右的短文，介绍为什么备份要分三份。只输出正文。', 128)

# 3) 判断力三题（同一批文件清单）
files = '目录 /tmp/bench-dir 下有这些文件：\n阿凡达_1080p.mkv\n阿凡达_720p.mkv\n游戏补丁_v1.2.3.zip\n游戏补丁_v1.10.0.zip\n三体_E01.mkv\n三体_E02.mkv\n三体_E03.mkv\n三体_E10.mkv\n'
q = files + '\n回答三件事，每件事单独一行，不要解释：\n1. 游戏补丁文件哪个版本更新？只回答文件名。\n2. 阿凡达的两个文件是同一部电影的不同清晰度版本吗？回答是或否，并指出哪个清晰度更高。\n3. 三体剧集按集数从小到大排序，只列文件名，用逗号分隔。'
rec['judgment'] = gen(q, 220)

rec['ps_after'] = ps()
with open(a.out, 'a', encoding='utf-8') as f:
    f.write(json.dumps(rec, ensure_ascii=False) + '\n')

print(json.dumps(rec, ensure_ascii=False, indent=1))
