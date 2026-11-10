#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan-guard.py - 防挤压 / 防卡点 / 防重复 / 每日一个拍板（2026-10-28 主公令，写进程序）

--dup "标题"        查重：与未结+近30天已结任务比相似度，>=0.55 判疑似重复，exit 6
--squeeze           挤压体检：积压周数=未结/周产能；>8 周告警，>16 周严重，exit 7
--stuck             卡点体检：阻塞项缺复查日期/已过期，或闲置>21天，exit 8
--decision          每日只出 1 个待拍板（按 prio+闲置 打分最高者），其余列出但标"自决"
--all               三者全跑
"""
import json, os, re, sqlite3, sys, datetime as dt
from collections import Counter

WS = "/home/j/.openclaw/workspace"
DB = os.path.join(WS, "state/tasks/tasks.db")
WORK = os.path.join(WS, "state/work")
OPEN_ST = ("pending", "open", "in_progress", "paused")

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def toks(s):
    s = (s or "").lower()
    s = re.sub(r"【[^】]*】|\[[^\]]*\]", "", s)   # 【待拍板】/ [28] 之类前缀不参与查重
    out = set(re.findall(r"[a-z0-9]{2,}", s))
    cjk = re.findall(r"[\u4e00-\u9fff]+", s)
    for seg in cjk:
        for i in range(len(seg) - 1):
            out.add(seg[i:i+2])
    return out

def sim(a, b):
    A, B = toks(a), toks(b)
    if not A or not B: return 0.0
    return len(A & B) / float(len(A | B))

def cmd_dup(title, thresh=0.55):
    c = conn()
    cands = []
    for r in c.execute("select no,title,status from tasks"):
        if not r["title"]: continue
        s = sim(title, r["title"])
        if s >= thresh: cands.append((round(s, 2), r["no"], r["status"], r["title"]))
    cands.sort(reverse=True)
    if cands:
        print("疑似重复（阈值 %.2f）：" % thresh)
        for s, no, st, t in cands[:5]:
            print("  %.2f  #%s [%s] %s" % (s, no, st, t[:46]))
        print("处理：合并到现有条目（events 留痕）或加 --force 强行新建")
        return 6
    print("查重通过：无相似任务")
    return 0

def cap_week(c):
    since = (dt.date.today() - dt.timedelta(weeks=8)).isoformat()
    rows = [r[0] for r in c.execute("select ts from events where field='status' and new='done' and ts>=?", (since,))]
    wk = Counter()
    for ts in rows:
        try: wk[dt.date.fromisoformat(ts[:10]).isocalendar()[1]] += 1
        except Exception: pass
    if not wk: return 1.0
    vals = sorted(wk.values())
    return float(vals[len(vals)//2])

def cmd_squeeze():
    c = conn()
    open_n = c.execute("select count(*) from tasks where status in ('pending','open','in_progress','paused') and coalesce(blocked,0)=0 and (select max(ts) from events e where e.no=tasks.no and coalesce(e.actor,'')!='migrate' and e.field not in ('import','who')) >= date('now','-21 day')").fetchone()[0]
    blocked_n = c.execute("select count(*) from tasks where status in ('pending','open','in_progress','paused') and coalesce(blocked,0)=1").fetchone()[0]
    cap = cap_week(c)
    weeks = open_n / cap if cap else 999
    lvl = "严重" if weeks > 16 else ("告警" if weeks > 8 else "正常")
    print("挤压体检：在办 %d 项 / 周产能 %.1f 项 = 积压 %.1f 周 -> %s（阻塞 %d 项另计）" % (open_n, cap, weeks, lvl, blocked_n))
    if lvl != "正常":
        print("  规则：积压>8 周必须停止新增，只做关闭；>16 周必须砍单（砍到 8 周以内）")
        return 7
    return 0

def cmd_stuck():
    c = conn(); today = dt.date.today()
    bad = []
    for r in c.execute("select no,title,blocked,blocked_reason,blocked_until from tasks where status in ('pending','open','in_progress','paused') and coalesce(blocked,0)=1"):
        if not r["blocked_reason"]: bad.append("卡点无原因：#%s %s" % (r["no"], (r["title"] or "")[:36]))
        elif not r["blocked_until"]: bad.append("卡点无复查日期：#%s %s" % (r["no"], (r["title"] or "")[:36]))
        else:
            try:
                if dt.date.fromisoformat(r["blocked_until"]) < today:
                    bad.append("复查已过期(%s)：#%s %s" % (r["blocked_until"], r["no"], (r["title"] or "")[:36]))
            except Exception:
                bad.append("复查日期格式错：#%s" % r["no"])
    since = (today - dt.timedelta(days=21)).isoformat()
    for r in c.execute("""select t.no,t.title from tasks t
        where t.status in ('pending','open','in_progress','paused') and coalesce(t.blocked,0)=0
          and not exists (select 1 from events e where e.no=t.no and e.ts>=?)""", (since,)):
        bad.append("闲置>21天：#%s %s" % (r["no"], (r["title"] or "")[:36]))
    if bad:
        print("卡点体检发现 %d 项：" % len(bad))
        for x in bad[:15]: print("  - " + x)
        if len(bad) > 15: print("  ...另有 %d 项" % (len(bad) - 15))
        return 8
    print("卡点体检：无异常")
    return 0

def has_review(c, no, days=7):
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    r = c.execute("select count(*) from events where no=? and field='review' and ts>=?", (no, since)).fetchone()
    return (r[0] or 0) > 0

def has_recent(c, no, days=21):
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    r = c.execute("select count(*) from events where no=? and ts>=? and coalesce(actor,'')!='migrate' and field not in ('import','who')", (no, since)).fetchone()
    return (r[0] or 0) > 0

def third_needed(c, no, days=7):
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    r = c.execute("select new from events where no=? and field='review' and ts>=? order by ts desc limit 1", (no, since)).fetchone()
    if not r: return False
    txt = (r[0] or "")
    if ("不一致" not in txt) and ("冲突" not in txt): return False
    r3 = c.execute("select count(*) from events where no=? and field in ('review3','review4') and ts>=?", (no, since)).fetchone()[0]
    return (r3 or 0) == 0

def cmd_decision():
    c = conn()
    rows = [dict(r) for r in c.execute("select no,title,prio,kind,notes,who from tasks where status in ('pending','open','in_progress') and coalesce(blocked,0)=0")]
    mine = [r for r in rows if (r.get("who") or "agent") != "owner"]
    mine = [r for r in mine if has_recent(c, r["no"])]
    rows = [r for r in rows if (r.get("who") or "agent") == "owner"]
    last = {}
    for r in c.execute("select no,max(ts) ts from events group by no"): last[r["no"]] = r["ts"]
    def sc(t):
        p = 99
        try: p = int(t["prio"])
        except Exception: p = 99
        idle = 0
        ts = last.get(t["no"])
        if ts:
            try: idle = (dt.date.today() - dt.date.fromisoformat(ts[:10])).days
            except Exception: idle = 0
        return (p * 10) - min(idle, 60) / 6.0
    rows.sort(key=lambda t: sc(t))
    if not rows:
        print("今日无待你拍板项；我这边的 %d 项按授权自决。" % len(mine)); return 0
    top = rows[0]
    if not has_review(c, top["no"]):
        print("今日待拍板项 #%s 尚未双审，按规则先送双审再呈报（不占今天拍板名额）" % top["no"])
        print("双审完成后用: tasks-db.py log %d review \"双审结论摘要\" 记录" % top["no"])
        return 9
    if third_needed(c, top["no"]):
        print("双审结论不一致，按规则先加第三审再抉择（本次不呈报）：完成第三审后用 tasks-db.py log %d review3 \"第三审结论\" 记录" % top["no"])
        return 9
    print("今日唯一待拍板：#%s [p%s] %s" % (top["no"], top["prio"], top["title"]))
    print("你这边另有 %d 项，按你说的只提 1 项，其余不催。" % (len(rows) - 1))
    print("我这边的 %d 项按授权双审后自决，结果进日报。" % len(mine))
    return 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print("用法: plan-guard.py --dup TITLE | --squeeze | --stuck | --decision | --all"); sys.exit(2)
    rc = 0
    if "--dup" in a:
        i = a.index("--dup"); title = a[i+1] if len(a) > i+1 else ""
        rc = max(rc, cmd_dup(title))
    if "--squeeze" in a or "--all" in a: rc = max(rc, cmd_squeeze())
    if "--stuck" in a or "--all" in a: rc = max(rc, cmd_stuck())
    if "--decision" in a or "--all" in a: rc = max(rc, cmd_decision())
    sys.exit(rc)
