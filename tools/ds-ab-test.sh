#!/usr/bin/env bash
# ds-ab-test.sh — DeepSeek 服务端工具 vs 现有搜索链 A/B（2026-11-14, v2 Anthropic Messages）
# 用法: DEEPSEEK_API_KEY=... TAVILY_API_KEY=... bash tools/ds-ab-test.sh [任务文件]
# 输出 state/work/ds-ab-<ts>.csv/.log；不打印 key
set -uo pipefail
TASKS="${1:-/home/j/.openclaw/workspace/state/work/ds-ab-tasks.txt}"
OUT="/home/j/.openclaw/workspace/state/work/ds-ab-$(date +%Y%m%d-%H%M%S).csv"
LOG="${OUT%.csv}.log"
PY=/home/j/.openclaw/venvs/tts312/bin/python
"$PY" - "$TASKS" "$OUT" "$LOG" <<'PYEOF'
import os,sys,json,time,re,urllib.request,urllib.error
tasks=[l.strip() for l in open(sys.argv[1],encoding='utf-8') if l.strip()]
out=open(sys.argv[2],'w',encoding='utf-8'); log=open(sys.argv[3],'w',encoding='utf-8')
DS=os.environ['DEEPSEEK_API_KEY']; TV=os.environ.get('TAVILY_API_KEY','')
B_BASE=os.environ.get('DS_BASE','https://api.deepseek.com')
out.write('task,a_chars,a_tokens_est,a_sec,b_in_tok,b_out_tok,b_sec,b_cites,b_ok\n')
def post(url,body,hdr,timeout=180):
    req=urllib.request.Request(url,data=json.dumps(body,ensure_ascii=False).encode('utf-8'),headers=hdr)
    t=time.time()
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8')), time.time()-t
def fetch(u,timeout=20):
    try:
        req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=timeout) as r: raw=r.read(400000)
        t=raw.decode('utf-8',errors='ignore')
        t=re.sub(r'(?is)<(script|style).*?</\1>',' ',t); t=re.sub(r'(?s)<[^>]+>',' ',t)
        return re.sub(r'\s+',' ',t).strip()[:6000]
    except Exception as e:
        log.write('FETCH_FAIL %s %s\n'%(u,str(e)[:60])); return ''
for q in tasks:
    a_chars=0; a_sec=0.0; a_tok=0
    if TV:
        try:
            j,dt=post('https://api.tavily.com/search',{'api_key':TV,'query':q,'max_results':5,'search_depth':'basic'},{'Content-Type':'application/json'},timeout=60)
            a_sec+=dt
            a_chars=sum(len(r.get('content') or '') for r in (j.get('results') or []))
            for u in [r.get('url','') for r in (j.get('results') or [])][:3]:
                a_chars+=len(fetch(u))
            a_tok=int(a_chars/1.8)
        except Exception as e:
            log.write('A_FAIL %s %s\n'%(q,str(e)[:80]))
    b={'i':0,'o':0,'sec':0.0,'cites':0,'ok':0}
    try:
        body={'model':'deepseek-flash','max_tokens':1024,'stream':False,
              'messages':[{'role':'user','content':q}],
              'tools':[{'type':'deepseek_read_url','name':'deepseek_read_url'},{'type':'deepseek_web_search','name':'deepseek_web_search'}]}
        j,dt=post(B_BASE+'/anthropic/v1/messages',body,{'Content-Type':'application/json','x-api-key':DS,'anthropic-version':'2023-06-01'})
        u=j.get('usage') or {}
        cites=j.get('citations') or []
        if not cites:
            for blk in (j.get('content') or []):
                cites+= (blk.get('citations') or []) if isinstance(blk,dict) else []
        b={'i':u.get('input_tokens',0),'o':u.get('output_tokens',0),'sec':dt,'cites':len(cites),'ok':1}
    except urllib.error.HTTPError as e:
        log.write('B_HTTP %s %s %s\n'%(e.code,q,e.read().decode('utf-8',errors='ignore')[:200]))
    except Exception as e:
        log.write('B_FAIL %s %s\n'%(q,str(e)[:80]))
    out.write('%s,%d,%d,%.1f,%d,%d,%.1f,%d,%d\n'%(q,a_chars,a_tok,a_sec,b['i'],b['o'],b['sec'],b['cites'],b['ok']))
    out.flush(); log.flush()
out.close(); log.close(); print('DONE',sys.argv[2])
PYEOF

