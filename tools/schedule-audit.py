#!/usr/bin/env python3
"""schedule-audit.py —— 定时任务窗口对表（真源：openclaw cron list）
用法:
  schedule-audit.py                 # 只体检，打印撞窗清单
  schedule-audit.py --write-doc     # 体检 + 重写 docs/时间表与窗口规则-20261031.md 第三节
判定窗口（与固定文档一致）:
  断网窗 04:00-06:05  重启红区 07:45-08:15  早高峰 09:00-12:00  午高峰 14:00-18:00
退出码: 0 无撞窗 / 1 有撞窗（可用于 cron 门禁）
"""
import json,subprocess,sys,re
DOC='/home/j/.openclaw/workspace/docs/时间表与窗口规则-20261031.md'
def jobs():
    out=subprocess.run(['openclaw','cron','list','--json'],capture_output=True,text=True,cwd='/home/j/.openclaw').stdout
    d=json.loads(out); return d.get('jobs',d) if isinstance(d,dict) else d
def parse(expr):
    p=expr.split()
    if len(p)<2: return None
    mi,ho=p[0],p[1]
    if not mi.isdigit() or not ho.isdigit(): return None
    return int(ho)*60+int(mi)
WINDOWS=[('断网窗',240,365),[],[('重启红区',465,495)],[('早高峰',540,720)],[('午高峰',840,1080)]]
BUCKETS=[('深夜 00:00-03:59',0,239),('断网静默 04:00-06:05',240,365),('早间 06:06-07:44',366,464),('重启红区 07:45-08:15',465,495),('上午 08:16-11:59',496,719),('午间 12:00-13:59',720,839),('午后 14:00-17:59',840,1079),('晚间 18:00-23:59',1080,1439)]
CRIT={'断网窗':('需要联网的','纯本地'),'重启红区':('无','重启自检链'),'早高峰':('主公紧急/打印组','非紧急模型任务'),'午高峰':('主公紧急/打印组','非紧急模型任务')}
def main():
    js=jobs(); items=[]; viol=[]
    for j in js:
        s=j.get('schedule') or {}
        if s.get('kind')!='cron': continue
        e=s.get('expr',''); t=parse(e)
        if t is None: continue
        items.append((t,j.get('name'),e)); 
        for label in ['断网窗','重启红区','早高峰','午高峰']:
            for w in [x for group in WINDOWS for x in (group if isinstance(group,list) else [])]:
                if isinstance(w,tuple) and w[0]==label:
                    _,lo,hi=w
                    if lo<=t<=hi: viol.append((label,'%02d:%02d'%(t//60,t%60),j.get('name'),e))
    print('定时任务总数:',len(items))
    if viol:
        print('\n【撞窗】',len(viol),'项')
        for label,tt,n,e in viol: print(f'  [{label}] {tt} {n} ｜ {e}')
    else:
        print('【撞窗】0 项 ✅')
    if '--write-doc' in sys.argv:
        lines=['## 三、全量时刻表（按时间排序，本表由 tools/schedule-audit.py 生成）','']
        for label,lo,hi in BUCKETS:
            sub=[x for x in items if lo<=x[0]<=hi]
            lines.append(f'### {label}（{len(sub)} 项）'); lines.append('')
            if not sub: lines+=['- （空）','']
            else:
                for t,n,e in sorted(sub): lines.append(f'- `{t//60:02d}:{t%60:02d}` {n} ｜ `{e}`')
                lines.append('')
        txt=open(DOC).read()
        start=txt.index('## 三、全量时刻表'); end=txt.index('## 四、')
        open(DOC,'w').write(txt[:start]+'\n'.join(lines)+'\n'+txt[end:])
        print('文档第三节已重写:',DOC)
    return 1 if viol else 0
sys.exit(main())

