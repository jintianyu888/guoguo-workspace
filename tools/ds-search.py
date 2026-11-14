#!/usr/bin/env python3
"""ds-search.py — DeepSeek 服务端联网搜索/读链接（2026-11-14 试点）

用法:
  ds-search.py "问题"                  # 联网搜索+自动读页
  ds-search.py --url https://... "要求"  # 只读指定链接
  选项: --json  --max-tokens N  --no-think

密钥: 环境变量 DEEPSEEK_APP_KEY，或 openclaw secrets store get DEEPSEEK_APP_KEY --plain
退出码: 0 成功 / 2 参数错 / 3 无密钥 / 4 网络错 / 5 接口错
"""
import os,sys,json,time,subprocess,urllib.request,urllib.error
BASE='https://api.deepseek.com/anthropic/v1/messages'
def get_key():
    k=os.environ.get('DEEPSEEK_APP_KEY','').strip()
    if k: return k
    try:
        out=subprocess.run(['openclaw','secrets','store','get','DEEPSEEK_APP_KEY','--plain'],capture_output=True,text=True,timeout=20)
        return (out.stdout or '').strip()
    except Exception:
        return ''
def call(key,msgs,url=None,max_tokens=900,think=True):
    tools=[{'type':'deepseek_read_url','name':'deepseek_read_url'}]
    if not url: tools.insert(0,{'type':'deepseek_web_search','name':'deepseek_web_search'})
    body={'model':'deepseek-flash','max_tokens':max_tokens,'messages':msgs,'tools':tools}
    if not think: body['thinking']={'type':'disabled'}
    req=urllib.request.Request(BASE,data=json.dumps(body,ensure_ascii=False).encode(),
        headers={'Content-Type':'application/json','x-api-key':key,'anthropic-version':'2023-06-01'})
    t=time.time()
    with urllib.request.urlopen(req,timeout=120) as r:
        return json.loads(r.read().decode()), time.time()-t
def main(argv):
    if not argv: print(__doc__); return 2
    as_json=False; mt=900; url=None; think=True; args=[]; i=0
    while i<len(argv):
        a=argv[i]
        if a=='--json': as_json=True; i+=1
        elif a=='--no-think': think=False; i+=1
        elif a=='--max-tokens': mt=int(argv[i+1]); i+=2
        elif a=='--url': url=argv[i+1]; i+=2
        elif a in ('-h','--help'): print(__doc__); return 0
        else: args.append(a); i+=1
    q=' '.join(args).strip()
    if url and not q: q='请读取该链接并给出要点摘要'
    if not q: print('ERR: 缺少问题',file=sys.stderr); return 2
    key=get_key()
    if not key: print('ERR: 未取到 DEEPSEEK_APP_KEY',file=sys.stderr); return 3
    content=q if not url else q+chr(10)+chr(10)+'链接：'+url
    try:
        d,sec=call(key,[{'role':'user','content':content}],url=url,max_tokens=mt,think=think)
    except urllib.error.HTTPError as e:
        print('ERR: HTTP %s %s'%(e.code,e.read().decode('utf-8','ignore')[:300]),file=sys.stderr); return 5
    except Exception as e:
        print('ERR: %s'%str(e)[:200],file=sys.stderr); return 4
    txt=''; cites=[]
    for b in d.get('content') or []:
        t=b.get('type')
        if t=='text':
            txt+=(b.get('text') or '')
            for c in (b.get('citations') or []): cites.append(c.get('url') or c.get('title') or '')
        elif t=='web_search_tool_result':
            for it in (b.get('content') or []):
                u=it.get('url') or ''
                if u: cites.append(u)
    cites=[c for c in dict.fromkeys(cites) if c]
    u=d.get('usage') or {}
    if as_json:
        print(json.dumps({'answer':txt.strip(),'citations':cites,'usage':u,'seconds':round(sec,1)},ensure_ascii=False,indent=2)); return 0
    print(txt.strip())
    if cites:
        print(chr(10)+'来源：')
        for c in cites[:6]: print('- '+c)
    print(chr(10)+'[%d in / %d out tok, %.1fs]'%(u.get('input_tokens',0),u.get('output_tokens',0),sec),file=sys.stderr)
    return 0
if __name__=='__main__': sys.exit(main(sys.argv[1:]))

