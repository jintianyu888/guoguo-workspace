#!/usr/bin/env python3
# info-window-card.py v3 —— 信息窗状态卡（零 token，纯本地渲染）
# v3：把空白补满，新增 磁盘/额度/巡检/安防 段；全部数据带超时、取不到写 n/a
import json, os, subprocess, sys, datetime, shlex, zipfile
from PIL import Image, ImageDraw, ImageFont

W = 900
BG=(18,20,24); FG=(232,236,241); DIM=(140,150,162)
ACC=(94,176,255); OK=(72,199,142); WARN=(245,180,66); BAD=(240,96,96)
CJK="/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
LAT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
WS="/home/j/.openclaw/workspace"

def numf(v, default=None):
    """安全转数字：非数字/占位符一律回落 default，避免一条坏字段拖垮整段渲染"""
    try:
        if v is None: return default
        if isinstance(v,str):
            s=v.strip()
            if not s or s.lower() in ("n/a","-","unlimited","nan"): return default
            v=s
        return float(v)
    except Exception:
        return default

def sh(cmd, t=6):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t)
        return (r.stdout or "").strip()
    except Exception:
        return ""

_cache={}
def fnt(kind,sz):
    k=(kind,sz)
    if k not in _cache:
        try: _cache[k]=ImageFont.truetype(CJK if kind=="cjk" else LAT, sz)
        except Exception: _cache[k]=ImageFont.load_default()
    return _cache[k]

def is_cjk(ch):
    o=ord(ch)
    return (0x4E00<=o<=0x9FFF) or (0x3400<=o<=0x4DBF) or (0x3000<=o<=0x303F) or (0xFF00<=o<=0xFFEF) or (0x2E80<=o<=0x2EFF)

def segs(text):
    out=[]
    for ch in text:
        kind="cjk" if is_cjk(ch) else "lat"
        if out and out[-1][0]==kind: out[-1][1]+=ch
        else: out.append([kind,ch])
    return out

def measure(text,sz):
    tot=0
    for k,t in segs(text):
        tot+=fnt(k,sz).getlength(t)
    return tot

def draw(d,x,y,text,sz,fill,anchor="la"):
    text="" if text is None else str(text)
    total=measure(text,sz)
    if anchor[0]=="r": x=x-total
    elif anchor[0]=="m": x=x-total/2
    for k,t in segs(text):
        f=fnt(k,sz); d.text((x,y),t,font=f,fill=fill); x+=f.getlength(t)
    return total

SECTIONS=[]
def section(title, rows):
    rows=[(a,b,c) for (a,b,c) in rows if b is not None]
    if not rows: return
    SECTIONS.append((title, rows))

# ---------- 采集 ----------
state=sh("systemctl --user is-active openclaw-gateway") or "?"
pid=sh("pgrep -f 'openclaw.*gateway' | head -1")
health=sh("timeout 4 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health", 6) or "?"
try: rss="%.1f"%(int(sh("ps -o rss= -p "+pid).strip())/1048576) if pid else "?"
except Exception: rss="?"
cg=sh("systemctl --user show openclaw-gateway -p MemoryCurrent --value")
try: cg_g="%.1f"%(int(cg)/1073741824)
except Exception: cg_g="?"
up=sh("ps -o etime= -p "+pid).strip() if pid else ""
nre=sh("systemctl --user show openclaw-gateway -p NRestarts --value") or "?"
ok = state=="active" and health=="200"

load=sh("cut -d' ' -f1-3 /proc/loadavg")
def _cpupct():
    try:
        import time as _t
        def _s():
            v=list(map(int,open("/proc/stat").readline().split()[1:]))
            return sum(v), v[3]+v[4]
        x=_s(); _t.sleep(0.35); y=_s()
        dt=y[0]-x[0]; di=y[1]-x[1]
        return "%.0f%%" % (100.0*(1-di/dt)) if dt>0 else "n/a"
    except Exception:
        return "n/a"
cpupct=_cpupct()
procs=sh("ps -e --no-headers 2>/dev/null | wc -l").strip()
hostn=sh("hostname 2>/dev/null") or "-"
root_size=sh("timeout 4 df -h / | awk 'NR==2{print $2}'") or "-"
boot_at=sh("uptime -s 2>/dev/null") or "-"
kern=sh("uname -r") or "-"
memline=sh("free -m | sed -n '2p'").split()
swapline=sh("free -m | sed -n '3p'").split()
def mrow(parts):
    try:
        if len(parts)>=3:
            tot=int(parts[1]); used=int(parts[2])
            pct=int(used*100/tot) if tot else 0
            return "%.1f / %.1f GB (%d%%)"%(used/1024, tot/1024, pct), pct
    except Exception:
        pass
    return "n/a", None
mem_txt,mem_pct=mrow(memline)
swap_txt,swap_pct=mrow(swapline)
NVS="/usr/lib/wsl/lib/nvidia-smi"
if not os.path.exists(NVS): NVS=sh("command -v nvidia-smi")
gpu=""
if NVS:
    g=sh("%s --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader"%NVS)
    if g: gpu=" / ".join(x.strip() for x in g.split(","))

df=sh("timeout 4 df -hP / /mnt/e /mnt/h /mnt/d /mnt/x 2>/dev/null")
dk={}
for line in df.splitlines()[1:]:
    p=line.split()
    if len(p)>=6: dk[p[-1]]=(p[4], p[3])
def disk_row(mp, name):
    v=dk.get(mp)
    if not v: return (name, "n/a", DIM)
    pct=int(v[0].rstrip('%')) if v[0].rstrip('%').isdigit() else 0
    col = BAD if pct>=90 else (WARN if pct>=80 else FG)
    return (name, "%s 用 · 剩 %s"%(v[0], v[1]), col)

try: tasks=json.load(open(os.path.join(WS,"state/tasks/tasks.json"),encoding="utf-8"))
except Exception: tasks={}
items=(tasks.get("items") or []) if isinstance(tasks,dict) else (tasks if isinstance(tasks,list) else [])
today=datetime.date.today().isoformat()
prog=sum(1 for i in items if isinstance(i,dict) and i.get("status")=="in_progress")
pend=sum(1 for i in items if isinstance(i,dict) and i.get("status")=="pending")
openc=sum(1 for i in items if isinstance(i,dict) and i.get("status")=="open")
done=sum(1 for i in items if isinstance(i,dict) and i.get("status")=="done" and str(i.get("updated",""))[:10]==today)

# /mnt/e 是 9p 挂载：先探活，挂死时不做 ls/date/du，避免整张卡被拖住
e_ok = sh("timeout 3 ls /mnt/e >/dev/null 2>&1 && echo ok", 5) == "ok"
bk = sh("ls -t /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null | head -1") if e_ok else ""
bkinfo="-" if e_ok else "n/a（E 盘无响应）"; bkage=None
if bk:
    bkinfo="%s · %s"%(sh("date -r %s '+%%m-%%d %%H:%%M'"%shlex.quote(bk), 5), sh("du -h %s 2>/dev/null | cut -f1"%shlex.quote(bk), 20))
    try:
        age_h=(datetime.datetime.now().timestamp()-os.path.getmtime(bk))/3600
        bkage=age_h
        bkinfo += " · %.0f 小时前"%age_h
    except Exception: pass
bkcol = DIM if bkage is None else (BAD if bkage>50 else (WARN if bkage>30 else FG))

mm={}
try:
    bal=json.load(open(os.path.join(WS,"state/model-econ/balances.json"),encoding="utf-8"))
    pr=bal.get("providers",{})
    ds=pr.get("deepseek",{})
    _d=numf(ds.get("available"))
    dv="¥%.2f"%_d if _d is not None else "n/a"
    z=pr.get("zhipu",{})
    zv="5h %s%% · 周 %s%%"%(z.get("window_pct","n/a"), z.get("weekly_pct","n/a")) if z else "n/a"
    k=pr.get("kimi",{})
    kn=k.get("norm") or {}
    kpct=kn.get("month_pct", k.get("month_used_pct"))
    kv="本期已用(月卡) %s%%"%(kpct if kpct is not None else "n/a") if k else "n/a"
    mx=pr.get("minimax",{})
    mv="5h %s%% · 周 %s%%"%(mx.get("window_pct","n/a"), mx.get("week_pct", mx.get("weekly_pct","n/a"))) if mx else "n/a"
    mm["cap"]=bal.get("captured_at") or bal.get("updated_at")
except Exception:
    dv=zv=kv=mv="n/a"

st={}
try: st=json.load(open(os.path.join(WS,"state/stability/latest.json"),encoding="utf-8"))
except Exception: pass
cnt=st.get("counts") or {}
verdict=st.get("verdict") or "n/a"
stime=(st.get("ts") or "")[5:16]
nflog=os.path.join(WS,"state/notify-fail.log")
nf=sh("awk -v c=\"$(date -d '24 hours ago' '+%F %T')\" '/^[0-9][0-9][0-9][0-9]-/ {if (substr($0,1,19) >= c) n++} END{print n+0}' "+nflog, 8) or "n/a"
cron_fail="n/a"
_c=sh("timeout 6 openclaw cron list --json", 9)
if _c.startswith("[") or _c.startswith("{"):
    try:
        _o=json.loads(_c)
        jobs=_o.get("jobs", []) if isinstance(_o, dict) else _o
        bad=[j.get("name","?") for j in jobs if j.get("enabled") is not False and str(j.get("lastRunStatus","")).lower() in ("error","failed")]
        cron_fail="%d 个%s"%(len(bad), ("（"+bad[0][:12]+"…）") if bad else "")
    except Exception: pass

nv="n/a"
nlog=sh("ls -t %s/state/work/nvr-face-scan*.log 2>/dev/null | head -1"%WS)
if nlog:
    nv=sh("date -r '%s' '+%%m-%%d %%H:%%M'"%nlog, 5)
faces="n/a"
try: faces=str(len([x for x in os.listdir(os.path.join(WS,"state/faces/hits"))]))
except Exception: pass

# ---- 看门狗拉起次数（24h）与人脸库规模 ----
_wd=os.path.join(WS,"state/work/gateway-watchdog.log")
wd24=(sh("grep '拉起成功' %s 2>/dev/null | sed 's/^\\[//;s/\\].*//' | awk -v c=\"$(date -d '24 hours ago' '+%%F %%T')\" '$0>=c' | wc -l"%shlex.quote(_wd)).strip() or "0")
face_lib="n/a"
try:
    _z=zipfile.ZipFile(os.path.join(WS,"state/faces/collected.npz"))
    _n=max(0,(_z.getinfo("emb.npy").file_size-128)//2048)
    face_lib="空（未录入）" if _n==0 else "%d 张"%_n
except Exception:
    pass

# ---------- 双机 / OC 健康（2026-11-02 主公需求：信息窗要体现 A/B 机与 OC 健康稳定） ----------
HS={}
try:
    _j=sh("timeout 6 curl -s http://127.0.0.1:8899/api/health-summary", 8)
    if _j.startswith("{"): HS=json.loads(_j)
except Exception:
    HS={}
if not HS:
    # 接口不可用时回落离线历史文件（work 管家维护，每分钟采样）
    try:
        _h=json.load(open("/home/j/openclaw-workspaces/work/果果助手/data/health-history.json",encoding="utf-8"))
        if isinstance(_h,dict) and ("oc" in _h or "a" in _h): HS=_h
        else:
            _arr=_h.get("history") or _h.get("items") or []
            if _arr and isinstance(_arr[-1],dict): HS=_arr[-1]
    except Exception:
        HS={}
_ha=HS.get("a") or {}; _ho=HS.get("oc") or {}; _hb=HS.get("b") or {}
_hm=HS.get("machines") or {}; _ma=_hm.get("a") or {}; _mb=_hm.get("b") or {}
def _gb(v):
    try: return "%.1f"%(float(v)/1073741824)
    except Exception: return None
def _ago(ms):
    try:
        s=max(0,(datetime.datetime.now().timestamp()*1000-float(ms))/1000)
        return ("%.0f 秒前"%s) if s<90 else (("%.0f 分钟前"%(s/60)) if s<5400 else "%.1f 小时前"%(s/3600))
    except Exception: return "n/a"
def _used(mt,ma):
    try:
        mt=float(mt); ma=float(ma)
        u=mt-ma
        return "%.1f/%.1f GB（%d%%）"%(u/1073741824, mt/1073741824, round(u*100/mt))
    except Exception: return None
if _ha:
    _a_mem=numf(_ha.get("memPct"))
    _a_memtxt = ("%d%%"%int(_a_mem)) if (_a_mem is not None and _a_mem>0) else None
    if not _a_memtxt:
        _am=_used(_ma.get("memT"), _ma.get("memA"))
        _a_memtxt = _am.split("（")[-1].rstrip("）") if _am else "n/a"
    _a_txt="%s · %s · 内存 %s · 负载 %s · 磁盘 %s%%"%(
        ("● 在线" if ok else "○ 离线"), (_ma.get("ip") or "-"), _a_memtxt,
        ("%.2f"%numf(_ha.get("load"))) if numf(_ha.get("load")) is not None else "n/a",
        ("%s"%int(numf(_ha.get("diskPct")))) if numf(_ha.get("diskPct")) is not None else "n/a")
else:
    _a_txt="n/a（采集未就绪）"
_b_on=bool(_hb.get("on")); _b_pct=numf(_hb.get("onlinePct")); _b_drop=_hb.get("drops")
# 心跳时龄：b.on 可能是旧状态，心跳超 180 秒就当失联，不拿旧标志冒充在线
_b_age=None
try: _b_age=max(0,(datetime.datetime.now().timestamp()*1000-float(_hb.get("seen")))/1000)
except Exception: _b_age=None
_b_live = _b_on and (_b_age is not None and _b_age<180)
_b_mem=_used(_mb.get("memT"), _mb.get("memA"))
if _hb:
    _b_l1="%s · 心跳 %s · 24h 在线 %s%% · 掉线 %s"%(
        ("● 在线" if _b_live else ("● 心跳停" if _b_on else "○ 离线")), _ago(_hb.get("seen")),
        ("%s"%int(_b_pct)) if _b_pct is not None else "n/a",
        (_b_drop if _b_drop is not None else "n/a"))
    _b_l2="内存 %s · 磁盘剩 %s"%(_b_mem or "n/a", (_gb(_mb.get("diskA")) and (_gb(_mb.get("diskA"))+" GB")) or "n/a")
else:
    _b_l1=_b_l2="n/a（采集未就绪）"
_loop="正常" if (_ho.get("ok") and not _ho.get("degraded")) else ("降级" if _ho.get("degraded") else "异常")
_delay=numf(_ho.get("delayMaxMs")); _dq=_ho.get("dq"); _okp=numf(_ho.get("okPct"))
_col_loop = OK if _loop=="正常" else (WARN if _loop=="降级" else BAD)
_col_b = OK if (_b_on and (_b_pct is None or _b_pct>=95)) else (WARN if _b_on else BAD)

# ---------- 组装 ----------
section("网关",[
  ("状态", "%s / health %s"%(state, health), OK if ok else BAD),
  ("进程 / 运行时长", "%s · %s"%(pid or "无", up or "-"), FG),
  ("内存 RSS / cgroup", "%s / %s GiB"%(rss, cg_g), WARN if (numf(rss) or 0)>5.5 else FG),
  ("systemd 自动重启", str(nre), FG),
  ("看门狗拉起 24h", wd24, WARN if wd24[:1].isdigit() and int(wd24.split()[0])>0 else FG),
])
section("主机",[
  ("CPU 利用率（1-idle）/ 负载 1m", (cpupct+" / "+((load or "n/a").split()[0])), FG),
  ("内存（WSL）", mem_txt, WARN if mem_pct and mem_pct>85 else FG),
  ("Swap", swap_txt, WARN if swap_pct and swap_pct>60 else FG),
  ("GPU", gpu or "不可用", FG),
  ("进程 / 主机名", "%s 个 · %s"%(procs or "?", hostn), FG),
])
section("双机",[
  ("A 机"+((" · "+_ma.get("name")) if _ma.get("name") else ""), _a_txt, OK if ok else BAD),
  ("B 机"+((" · "+_mb.get("name")) if _mb.get("name") else ""), _b_l1, OK if _b_live else (WARN if _b_on else BAD)),
  ("B 机内存", _b_l2, FG),
])
section("OC 健康",[
  ("事件循环", "%s · 最大延迟 %s ms · 死信 %s"%(_loop, ("%.0f"%_delay) if _delay is not None else "n/a", _dq if _dq is not None else "n/a"), _col_loop),
  ("会话 / 通道 / 管家", "%s / %s / %s"%(_ho.get("sessions","n/a"), _ho.get("channels","n/a"), _ho.get("agents","n/a")), FG),
  ("24h 正常率", (("%.1f%%"%_okp) if _okp is not None else "n/a"), OK if (_okp is not None and _okp>=99) else WARN),
])
section("磁盘",[
  disk_row("/","根盘 /"),
  disk_row("/mnt/e","E:"),
  disk_row("/mnt/h","H:"),
  disk_row("/mnt/d","D:"),
  disk_row("/mnt/x","X:"),
])
section("任务",[
  ("在办", str(prog), FG),
  ("待拍板", str(pend), FG),
  ("未结待办", str(openc), FG),
  ("今日完成", str(done), OK),
])
section("备份",[
  ("最近工作区备份", bkinfo, bkcol),
  ("备份盘 E: 剩余", (dk.get("/mnt/e") or ("","?"))[1], FG),
])
section("模型额度",[
  ("DeepSeek 余额", dv, FG),
  ("智谱 GLM", zv, FG),
  ("Kimi", kv, FG),
  ("MiniMax", mv, FG),
])
section("巡检",[
  ("稳定性（每日 07:00）", "%s · PASS %s / WARN %s / FAIL %s · %s"%(verdict, cnt.get("pass","?"), cnt.get("warn","?"), cnt.get("fail","?"), stime), OK if verdict=="PASS" else (BAD if verdict=="FAIL" else WARN)),
  ("通知失败 24h", "%s 条"%nf, WARN if nf.isdigit() and int(nf)>0 else FG),
  ("定时任务失败", cron_fail, WARN if cron_fail[:1].isdigit() and int(cron_fail.split()[0])>0 else FG),
])
section("安防",[
  ("最近人脸扫描", nv, FG),
  ("人脸命中", faces + " 条", FG),
  ("人脸库", face_lib, WARN if face_lib.startswith("空") else FG),
])
section("系统",[
  ("内核", kern, FG),
  ("根盘总量 / 剩余", "%s / %s"%(root_size, (dk.get("/") or ("","?"))[1]), FG),
  ("开机时间", boot_at, FG),
])

# ---------- 增量：告警通道 ----------
hook_ok=os.path.exists(os.path.expanduser("~/.config/feishu-alert-webhook"))
hook_txt="已配置" if hook_ok else "未配置（回落网关推送）"
last_alert="无记录"
try:
    with open(nflog,encoding="utf-8",errors="replace") as _f:
        _ls=[x.rstrip("\n") for x in _f if x[:1].isdigit()]
    if _ls:
        _l=_ls[-1]
        _msg=_l[20:].strip()
        for _p in ("notify failed/timeout:", "notify failed:", "notify timeout:"):
            if _msg.startswith(_p): _msg=_msg[len(_p):].strip()
        last_alert=("%s %s"%(_l[5:16], _msg))[:44]
except Exception:
    pass
section("告警",[
  ("告警通道 webhook", hook_txt, FG if hook_ok else WARN),
  ("最近一条通知失败", last_alert, DIM),
])

# ---------- 布局 ----------
HEAD=76; SEC_H=36; ROW_H=30; FOOT=96
H = HEAD + sum(SEC_H + len(r)*ROW_H + 6 for _,r in SECTIONS) + FOOT
img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img); y=28
draw(d,36,y,"OpenClaw 信息窗",34,FG)
draw(d,W-36,y+6,datetime.datetime.now().strftime("%m-%d %H:%M"),26,DIM,"ra")
y+=54; d.line([(36,y),(W-36,y)],fill=(50,56,64),width=1); y+=22

for title, rows in SECTIONS:
    draw(d,36,y,title,26,ACC); y+=SEC_H
    for label,value,color in rows:
        draw(d,52,y+4,label,21,DIM)
        draw(d,W-36,y+3,value,22,color,"ra")
        y+=ROW_H
    y+=6

y=H-FOOT+30
d.line([(36,y),(W-36,y)],fill=(50,56,64),width=1)
draw(d,36,y+18,"果果 · 每小时自动更新",18,DIM)
draw(d,W-36,y+18,"异常会立刻加推一张",18,DIM,"ra")

out=sys.argv[1] if len(sys.argv)>1 else os.path.join(WS,"state/info-window/card.png")
os.makedirs(os.path.dirname(out),exist_ok=True); img.save(out,"PNG"); print(out)
