#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""butler-supervisor.py —— 果果自动监督五大管家（零 token，systemd 定时跑）
判定四类异常并只在有异常时推送：
 1 空转：6 小时内既无 cron 回执、也无工作区文件变化（08:00-22:00 生效）
 2 自审缺/败：当天自审 cron 无 ok 回执
 3 计划缺：自审文件缺 PLAN| 机器块
 4 无证据完成：tasks 里 agent=该管家 且 status=done 但 verify 为空
去重：每类每管家每天最多 1 次（state/supervisor/sent-<date>.json）
"""
import sqlite3, os, time, json, datetime, subprocess, sys

WS = "/home/j/.openclaw/workspace"
CDB = "/home/j/.openclaw/state/openclaw.sqlite"
STATE = os.path.join(WS, "state/supervisor")
BUTLERS = [("maint","维护管家","/home/j/openclaw-workspaces/maint"),
           ("backup","备份管家","/home/j/.openclaw/workspace-backup"),
           ("model","模型管家","/home/j/.openclaw/workspace-model"),
           ("work","干活管家","/home/j/openclaw-workspaces/work"),
           ("sheet-music","Hermess","/home/j/openclaw-workspaces/sheet-music")]
IDLE_HOURS = 6
PLAN_GRACE = "2026-11-08"  # 机器块机制 11-07 13:58 才上线，11-08 起才考核

os.makedirs(STATE, exist_ok=True)
today = datetime.date.today().isoformat()
sentf = os.path.join(STATE, "sent-%s.json" % today)
sent = json.load(open(sentf)) if os.path.exists(sentf) else {}

def q(sql, args=()):
    try:
        c = sqlite3.connect(CDB); c.row_factory = sqlite3.Row
        rows = c.execute(sql, args).fetchall(); c.close(); return rows
    except Exception:
        return []

def recent_ws_change(path, hours=IDLE_HOURS):
    cut = time.time() - hours*3600
    newest = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ('.git','node_modules','media','.cache')]
        for f in files:
            p = os.path.join(root, f)
            try:
                m = os.path.getmtime(p)
            except Exception:
                continue
            if m > newest: newest = m
        if newest > cut: return newest
    return newest

def review_status(agent):
    js = q("select job_id,job_json from cron_jobs")
    for r in js:
        j = json.loads(r["job_json"] or "{}")
        nm = j.get("name") or ""
        if "自审" in nm and (j.get("agentId") == agent or agent in nm):
            since = int(time.time()*1000) - 36*3600*1000
            rr = q("select status,started_at_ms from cron_run_receipts where job_id=? and started_at_ms>=? order by started_at_ms desc limit 1", (r["job_id"], since))
            return (rr[0]["status"], rr[0]["started_at_ms"]) if rr else ("missing", None), r["job_id"]
    return ("nojob", None), None

def plan_block_ok(agent, base):
    d = datetime.date.today()
    cands = [os.path.join(base, "state/self-review"), os.path.join(WS, "state/self-review")]
    names = [d.strftime("%Y%m%d")+".md", d.isoformat()+".md"]
    for b in cands:
        for n in names:
            p = os.path.join(b, n)
            if os.path.exists(p):
                t = open(p, encoding="utf-8", errors="ignore").read()
                return ("PLAN|" in t or "PLAN｜" in t), p
    return None, None

def push(msg):
    # 2026-11-08 20:40：监督消息属异常才响，走告警 webhook 线（普通 maint 线 20:00/20:20 连续发送失败）；
    # 截断 900 字避免超长 400。
    subprocess.run(["bash", os.path.join(WS, "tools/notify.sh"), "--alert", str(msg)[:900]],
                   capture_output=True, text=True, timeout=60)

finds = []
now_h = datetime.datetime.now().hour
for aid, cn, base in BUTLERS:
    # 1 空转
    rr = q("select max(started_at_ms) m from cron_run_receipts where agent_id=?", (aid,))
    last_run = (rr[0]["m"] or 0)/1000 if rr else 0
    last_file = recent_ws_change(base) if os.path.isdir(base) else 0
    last_act = max(last_run, last_file)
    if 8 <= now_h < 22 and (time.time() - last_act) > IDLE_HOURS*3600:
        hrs = int((time.time()-last_act)/3600) if last_act else 999
        finds.append((aid, cn, "空转", "%d 小时无 cron 回执、无工作区文件变化" % hrs))
    # 2 自审
    (st, ts), jid = review_status(aid)
    if st in ("missing", "nojob"):
        finds.append((aid, cn, "自审缺", "今日无自审回执" + ("" if jid else "（且找不到自审任务）")))
    elif st != "ok":
        finds.append((aid, cn, "自审失败", "最近一次自审状态=%s" % st))
    # 3 计划缺
    ok, p = plan_block_ok(aid, base)
    if ok is False and today >= PLAN_GRACE:
        finds.append((aid, cn, "计划缺", "自审文件无 PLAN| 机器块：%s" % p))
    # 4 无证据完成
    nv = q("select count(*) n from tasks where agent=? and status='done' and (verify is null or verify='')", (aid,))
    if nv and nv[0]["n"] > 0:
        finds.append((aid, cn, "完成无验收", "%d 项 done 但没有 verify 命令" % nv[0]["n"]))


def prune_subagents(max_age_h=24, cap=30):
    """清掉过期的子任务会话记录（先归档 key 清单）"""
    import subprocess as sp
    try:
        j = sp.run(["openclaw","sessions","--all-agents","--json"], capture_output=True, text=True, timeout=60, cwd="/home/j")
        d = json.loads(j.stdout); ss = d.get("sessions") or d
    except Exception:
        return 0
    now = time.time()*1000
    old = [x for x in ss if ":subagent:" in str(x.get("key","")) and (now-(x.get("updatedAt") or 0)) > max_age_h*3600000]
    if not old:
        return 0
    arc = os.path.join(STATE, "pruned-%s.jsonl" % today)
    with open(arc, "a") as f:
        for x in old[:cap]: f.write(json.dumps(x, ensure_ascii=False)+"\n")
    n = 0
    for x in old[:cap]:
        r = sp.run(["openclaw","gateway","call","sessions.delete","--params", json.dumps({"key": x["key"]})], capture_output=True, text=True, timeout=60, cwd="/home/j")
        if r.returncode == 0: n += 1
    return n

# 5 近期任务失败（90 分钟内），失败即提醒，不等下次
fails = []
try:
    c = sqlite3.connect(CDB); c.row_factory = sqlite3.Row
    since = int((time.time()-90*60)*1000)
    rows = c.execute("select r.job_id,r.status,r.error_text,r.started_at_ms,j.job_json from cron_run_receipts r join cron_jobs j on j.job_id=r.job_id where r.started_at_ms>=? and r.status!='ok' order by r.started_at_ms desc limit 20",(since,)).fetchall()
    c.close()
    seen=set()
    for r in rows:
        j=json.loads(r["job_json"] or "{}"); nm=j.get("name") or r["job_id"]
        if nm in seen: continue
        seen.add(nm)
        err=(r["error_text"] or r["status"] or "")[:70]
        key="job:%s" % nm
        if sent.get(key): continue
        sent[key]=int(time.time())
        fails.append("· 任务【%s】失败：%s（我会立刻排查，不让它等到下次）" % (nm, err))
except Exception:
    pass

REPORT_ONLY = "--report-only" in sys.argv
if REPORT_ONLY:
    if not finds:
        print("NO_ANOMALY")
    else:
        for aid, cn, kind, detail in finds:
            print("· %s【%s】%s" % (cn, kind, detail))
    sys.exit(0)

out = []
for aid, cn, kind, detail in finds:
    key = "%s:%s" % (aid, kind)
    if sent.get(key): continue
    sent[key] = int(time.time())
    out.append("· %s【%s】%s" % (cn, kind, detail))

if out or fails:
    body = "\n".join(fails + out)
    msg = "🔍 监督 %s\n%s\n\n处理：异常我立刻接手；连续 2 天同类升级为主公待办。" % (datetime.datetime.now().strftime("%m-%d %H:%M"), body)
    push(msg)
    print(msg)
else:
    print("no anomaly")
pruned = prune_subagents()
if pruned: print("已清理过期子任务会话 %d 条" % pruned)
json.dump(sent, open(sentf, "w"))
