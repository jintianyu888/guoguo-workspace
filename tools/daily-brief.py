#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daily-brief.py —— 果果每日简报（早/晚各一次）
用法: daily-brief.py [morning|evening]
数据源: state/tasks/tasks.json（唯一真源）
输出: 纯文本，适合飞书直发（不用表格）
"""
import json,os,sys,time,datetime

WS='/home/j/.openclaw/workspace'
LED=os.path.join(WS,'state/tasks/tasks.json')
PRIO=os.path.join(WS,'state/tasks/priority-order.md')
OWNER=(117,162,64,68,143)

def days_ago(ts):
    if not ts: return None
    try:
        s=str(ts).replace('Z','')[:19]
        dt=datetime.datetime.fromisoformat(s)
        return round((datetime.datetime.now()-dt).total_seconds()/86400,1)
    except Exception:
        return None

def tail_note(n,limit=60):
    if not n: return ''
    last=str(n).split('｜')[-1].strip()
    return last[:limit]

def main():
    slot=sys.argv[1] if len(sys.argv)>1 else 'morning'
    d=json.load(open(LED,encoding='utf-8'))
    items=[i for i in d['items'] if isinstance(i,dict)]
    today=datetime.date.today().isoformat()

    by={}
    for i in items: by.setdefault(i.get('status'),[]).append(i)
    done=len(by.get('done',[])); canc=len(by.get('cancelled',[]))
    live=[i for i in items if i.get('status') not in ('done','cancelled')]
    done_today=[i for i in by.get('done',[]) if str(i.get('updated','')).startswith(today)]

    head='☀️ 早上好，今日开工简报' if slot=='morning' else '🌙 收工简报'
    L=[]
    L.append('%s — %s'%(head,datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
    L.append('')
    L.append('【一、总览】未结 %d 项｜今日办完 %d 项｜累计办完 %d 项'%(len(live),len(done_today),done))
    cnt=' '.join('%s %d'%(k,len(v)) for k,v in sorted(by.items()) if k not in ('done','cancelled'))
    L.append('　状态分布：'+cnt)

    # 二、正在办
    ip=by.get('in_progress',[])
    L.append('')
    L.append('【二、正在办 %d 项】'%len(ip))
    for i in ip[:8]:
        dd=days_ago(i.get('updated'))
        age='（%s 天没动）'%dd if dd and dd>=1 else ''
        L.append('　· #%s %s%s'%(i.get('no'),str(i.get('title'))[:44],age))
        nt=tail_note(i.get('notes'))
        if nt: L.append('　　 进展：'+nt)

    # 三、等你拍板
    own=[i for i in live if i.get('no') in OWNER]
    if own:
        L.append('')
        L.append('【三、只能你办 %d 项】'%len(own))
        for i in own: L.append('　· #%s %s'%(i.get('no'),str(i.get('title'))[:50]))

    # 四、按主题分组（同类合并显示，不再逐条刷屏）
    q=[i for i in live if i.get('status') in ('pending','open')]
    L.append('')
    L.append('【四、待办 %d 项 · 按主题分组】'%len(q))
    grp={}
    for i in q: grp.setdefault(i.get('group') or '其他',[]).append(i)
    for g,arr in sorted(grp.items(), key=lambda kv:-len(kv[1])):
        L.append('　◆ %s（%d）'%(g,len(arr)))
        for i in arr[:3]:
            L.append('　　· #%s %s'%(i.get('no'),str(i.get('title'))[:44]))
        if len(arr)>3: L.append('　　… 另 %d 项'%(len(arr)-3))

    # 五、今日办完
    if done_today:
        L.append('')
        L.append('【五、今日办完 %d 项】'%len(done_today))
        for i in done_today[:8]:
            L.append('　· #%s %s'%(i.get('no'),str(i.get('title'))[:50]))

    # 六、今日问题与修复
    fixed=[]
    for i in items:
        if not str(i.get('updated','')).startswith(today): continue
        n=str(i.get('notes') or '')
        if any(k in n for k in ('根因','修复','发现','错误','失败','误判')):
            fixed.append((i.get('no'),tail_note(n,70)))
    if fixed:
        L.append('')
        L.append('【六、今日问题/修复 %d 条】'%len(fixed))
        for no,nt in fixed[:5]: L.append('　· #%s %s'%(no,nt))

    # 七、卡点
    paused=by.get('paused',[])+by.get('quarantine',[])
    if paused:
        L.append('')
        L.append('【七、卡住/隔离 %d 项】'%len(paused))
        for i in paused[:5]: L.append('　· #%s %s'%(i.get('no'),str(i.get('title'))[:48]))

    # 八、疑似僵尸：超 7 天未动的在办/排队项
    stale=[]
    for i in live:
        dd=days_ago(i.get('updated'))
        if dd is not None and dd>=7 and i.get('status') in ('pending','open','in_progress','paused'):
            stale.append((dd,i))
    if stale:
        stale.sort(key=lambda x: -x[0])
        L.append('')
        L.append('【八、疑似僵尸 %d 项（超 7 天没动，需核对是否已完成）】'%len(stale))
        for dd,i in stale[:6]:
            L.append('　· #%s %.0f 天｜%s'%(i.get('no'),dd,str(i.get('title'))[:40]))

    L.append('')
    L.append('—— 回我「调整 #编号」我就改方向；回「1-3 批」按待批台执行')
    print('\n'.join(L))

if __name__=='__main__':
    main()
