#!/usr/bin/env python3
"""dashboard-gen.py — 生成零依赖静态看板（老 iPad / 任何浏览器可看）
数据源：state/model-econ/balances.json、state/stability/latest.json、state/tasks/tasks.json、/proc、nvidia-smi
输出：state/portal/simple-dashboard.html（每 60 秒自动刷新，无需 JS）
用法：python3 tools/dashboard-gen.py [--quiet]
"""
import json,os,subprocess,sys,time,html

WS='/home/j/.openclaw/workspace'
OUT=os.path.join(WS,'state/portal')
os.makedirs(OUT,exist_ok=True)

def jload(rel,default=None):
    try:
        return json.load(open(os.path.join(WS,rel),encoding='utf-8'))
    except Exception:
        return default if default is not None else {}

def run(cmd,timeout=10):
    try:
        return subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=timeout).stdout.strip()
    except Exception:
        return ''

def e(v):
    return html.escape(str(v))

def card(title,rows,tone=''):
    body=''.join('<div class="row"><span class="k">%s</span><span class="v">%s</span></div>'%(e(k),e(v)) for k,v in rows)
    return '<div class="card %s"><div class="h">%s</div>%s</div>'%(tone,e(title),body)

# ---- 余额 ----
bal=jload('state/model-econ/balances.json',{})
prov=bal.get('providers',{}) or {}
def num(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool)

rows=[]
for key in ('deepseek','zhipu','kimi','minimax'):
    p=prov.get(key) or {}
    if not p: continue
    n=p.get('norm') or {}
    label=n.get('label') or key
    unit=n.get('unit') or p.get('currency') or ''
    bits=[]
    av=n.get('available')
    if not num(av): av=p.get('available')
    if num(av): bits.append('余额 %.2f %s'%(av,unit))
    m=p.get('month_used_pct')
    if num(m): bits.append('本月 %.0f%%'%m)
    r=p.get('rate_limit_pct')
    if num(r): bits.append('频限 %.0f%%'%r)
    tb=p.get('topup_balance')
    if num(tb) and tb: bits.append('加油包 %.2f'%tb)
    for k2,name2 in (('h5','5h'),('week','周')):
        sub=n.get(k2)
        if isinstance(sub,dict) and num(sub.get('pct')):
            bits.append('%s %.0f%%'%(name2,sub['pct']))
    if num(n.get('h5_pct')) and not any('5h' in b for b in bits): bits.append('5h %.0f%%'%n['h5_pct'])
    if num(n.get('week_pct')) and not any('周' in b for b in bits): bits.append('周 %.0f%%'%n['week_pct'])
    wp=p.get('window_pct'); wkp=p.get('weekly_pct')
    if num(wp) and not any('5h' in b for b in bits): bits.append('5h窗口 %.0f%%'%wp)
    if num(wkp) and not any('周' in b for b in bits): bits.append('周 %.0f%%'%wkp)
    if not bits and isinstance(p.get('used_pct'),str) and p['used_pct'].isdigit():
        bits.append('已用 %s%%'%p['used_pct'])
    pe=n.get('plan_expire') or p.get('plan_expire')
    if pe: bits.append('到期 %s'%str(pe)[:10])
    rows.append((label,' · '.join(bits) if bits else '暂无数据'))
if not rows: rows=[('余额','暂无数据')]
cap=bal.get('captured_at') or bal.get('updated_at') or ''
balances_card=card('额度 / 余额',rows+[('数据时间',cap or '—')])

# ---- 主机 ----
load=open('/proc/loadavg').read().split()[:3] if os.path.exists('/proc/loadavg') else ['-','-','-']
mem={}
for ln in open('/proc/meminfo'):
    k=ln.split(':')[0]
    if k in ('MemTotal','MemAvailable'): mem[k]=int(ln.split()[1])//1024
mt,ma=mem.get('MemTotal',0),mem.get('MemAvailable',0)
memtxt='%d/%d MB (%.0f%% 已用)'%(mt-ma,mt,(mt-ma)/mt*100) if mt else '—'
nvs='/usr/lib/wsl/lib/nvidia-smi'
if not os.path.exists(nvs): nvs='nvidia-smi'
gpu=run(nvs+' --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader')
gpu=gpu.replace('\r','')
if gpu:
    parts=[x.strip() for x in gpu.split(',')]
    gputxt='%s · %s%% · %s / %s'%(parts[0],parts[1],parts[2],parts[3]) if len(parts)>=4 else gpu
else:
    gputxt='未采集'
def dfp(p):
    try:
        s=os.statvfs(p); tot=s.f_blocks*s.f_frsize; free=s.f_bavail*s.f_frsize
        return '%.0f%% 已用（剩 %.0fG）'%((1-free/tot)*100,free/1e9)
    except Exception:
        return '—'
host_card=card('主机',[('负载 1/5/15 分钟',' / '.join(load)),('内存',memtxt),
                      ('系统盘 /',dfp('/')),('E 盘',dfp('/mnt/e')),('X 盘',dfp('/mnt/x')),('GPU',gputxt)])

# ---- 体检 ----
st=jload('state/stability/latest.json',{})
c=st.get('counts') or {}
v=st.get('verdict') or '—'
tone='ok' if str(v).upper().startswith('PASS') else ('warn' if 'WARN' in str(v).upper() else 'bad')
stab_card=card('体检',[('结论',v),('PASS/WARN/FAIL/SKIP','%s / %s / %s / %s'%(c.get('PASS','-'),c.get('WARN','-'),c.get('FAIL','-'),c.get('SKIP','-'))),
                      ('时间',st.get('ts','—'))],tone)

# ---- 待办 ----
td=jload('state/tasks/tasks.json',{})
its=[i for i in td.get('items',[]) if isinstance(i,dict)]
cnt={}
for i in its: cnt[i.get('status')]=cnt.get(i.get('status'),0)+1
pend=[i for i in its if i.get('status')=='pending']
rows=[('待办',cnt.get('pending',0)),('在办',cnt.get('in_progress',0)),('今日完成',cnt.get('done',0))]
for i in pend[:6]:
    rows.append(('[%s]'%i.get('no','?'),(i.get('title') or '')[:40]))
todo_card=card('待办',rows)

now=time.strftime('%Y-%m-%d %H:%M:%S')
page='''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>果果看板</title>
<style>
body{margin:0;padding:16px;background:#0f1319;color:#e8edf3;font-family:-apple-system,"PingFang SC","Helvetica Neue",Arial,sans-serif;}
.top{font-size:15px;color:#8fa2b8;margin-bottom:12px;}
.big{font-size:34px;font-weight:700;color:#fff;margin:2px 0 14px;}
.card{background:#18202b;border-radius:14px;padding:14px 16px;margin-bottom:14px;border-left:6px solid #2f7fd6;}
.card.ok{border-left-color:#2fae5b;} .card.warn{border-left-color:#d69a2f;} .card.bad{border-left-color:#d6442f;}
.h{font-size:21px;font-weight:700;color:#9fc4e8;margin-bottom:10px;}
.row{display:block;padding:6px 0;border-bottom:1px solid #232d3a;font-size:22px;line-height:1.45;}
.row:last-child{border-bottom:none;}
.k{color:#8fa2b8;margin-right:10px;}
.v{color:#f2f6fa;font-weight:600;}
.foot{color:#5d6c7d;font-size:15px;text-align:center;padding:10px 0 24px;}
</style></head><body>
<div class="top">果果看板 · 每 60 秒自动刷新</div>
<div class="big">%s</div>
%s
%s
%s
%s
<div class="foot">数据时间 %s · 生成于 A 机</div>
</body></html>'''%(e(now),balances_card,host_card,stab_card,todo_card,e(cap or '—'))
tmp=os.path.join(OUT,'simple-dashboard.html.tmp')
open(tmp,'w',encoding='utf-8').write(page)
os.replace(tmp,os.path.join(OUT,'simple-dashboard.html'))
if '--quiet' not in sys.argv:
    print('written',os.path.join(OUT,'simple-dashboard.html'),len(page),'bytes')
