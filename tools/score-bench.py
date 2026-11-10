#!/usr/bin/env python3
# score_bench.py — 按题库 scorer 给 raw 输出打分（不调模型，纯读取）
import json, os, re, sys
WS='/home/j/.openclaw/workspace'
BANK=WS+'/tools/model-bench/bank/items.jsonl'
items={}
for l in open(BANK):
    it=json.loads(l); items[it['id']]=it
def score(it, text):
    sc=it.get('scorer'); ex=it.get('expect'); t=(text or '').strip()
    if sc=='numbered_lines':
        n=len(re.findall(r'^\s*\d+[.、)]', t, re.M)); return (n==ex), 'lines=%d'%n
    if sc=='regex':
        return bool(re.search(ex, t, re.M)), ''
    if sc=='contains_all':
        miss=[s for s in ex if s not in t]; return (not miss), 'miss=%s'%miss
    if sc=='contains_any':
        return any(s in t for s in ex), ''
    if sc=='json':
        try:
            m=re.search(r'\{.*\}', t, re.S); obj=json.loads(m.group(0)) if m else None
            if not isinstance(obj,dict): return False,'not-dict'
            miss=[k for k in ex if k not in obj]; return (not miss), 'miss=%s'%miss
        except Exception as e: return False, 'json-err'
    if sc=='exact':
        return t.replace(' ','')==str(ex), t[:20]
    return None, 'manual'
def run_dir(d):
    out={}
    for model in sorted(os.listdir(d)):
        mdir=os.path.join(d,model); rows=[]
        if not os.path.isdir(mdir): continue
        for f in sorted(os.listdir(mdir)):
            try: r=json.load(open(os.path.join(mdir,f)))
            except Exception: continue
            iid=r.get('item');
            it=items.get(iid)
            if not it: continue
            ok,note=score(it, r.get('text') or r.get('out') or '')
            rows.append({'id':iid,'ok':ok,'note':note,'secs':r.get('latency_s'),'chars':len((r.get('text') or '')),'prompt_chars':r.get('prompt_chars'),'err':bool(r.get('error'))})
        out[model]=rows
    return out
for d in sys.argv[1:]:
    res=run_dir(d)
    print('==',os.path.basename(d))
    for m,rows in res.items():
        auto=[x for x in rows if x['ok'] is not None]
        passed=[x for x in auto if x['ok']]
        secs=[x['secs'] for x in rows if x['secs']]
        avg=sum(secs)/len(secs) if secs else 0
        print('  %-28s %d/%d  平均%.1fs  条目:%s' % (m, len(passed), len(auto), avg, ' '.join(('%s:%s'%(x['id'],'P' if x['ok'] else ('M' if x['ok'] is None else 'F'))) for x in rows)))