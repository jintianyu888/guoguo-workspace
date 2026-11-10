#!/usr/bin/env python3
# session-hygiene.py —— 会话体积巡检（只读）
# 依据 docs/会话卫生与事件循环保护规则-20261101.md
# rc: 0 正常 / 1 超硬阈 / 2 环境异常
import sqlite3, os, sys, glob, datetime, json

AGENTS_DIR = "/home/j/.openclaw/agents"
OUT_DIR = "/home/j/.openclaw/workspace/state/work"
SOFT_EV, SOFT_MB = 14000, 14.0
HARD_EV, HARD_MB = 20000, 20.0
ACTIVE_HOURS = 1

def now():
    return datetime.datetime.now().astimezone()

def scan(db):
    rows = []
    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    try:
        q = """select session_id, count(*),
               sum(coalesce(length(event_json),0)+coalesce(length(event_zstd),0)),
               max(created_at)
               from transcript_events group by session_id"""
        for sid, n, b, mx in c.execute(q):
            rows.append((sid, n, (b or 0)/1048576.0, mx))
    finally:
        c.close()
    return rows

def main():
    if not os.path.isdir(AGENTS_DIR):
        print("AGENTS_DIR missing", file=sys.stderr); return 2
    lines, hard, soft = [], [], []
    cut_active = (now() - datetime.timedelta(hours=ACTIVE_HOURS)).timestamp()*1000
    dbs = sorted(glob.glob(os.path.join(AGENTS_DIR, "*", "agent", "openclaw-agent.sqlite")))
    if not dbs:
        print("no agent db found", file=sys.stderr); return 2
    total_ev = 0
    for db in dbs:
        agent = db.split("/agents/")[1].split("/")[0]
        try:
            rows = scan(db)
        except Exception as e:
            lines.append("- %s 读取失败: %s" % (agent, e)); continue
        for sid, n, mb, mx in rows:
            total_ev += n
            active = (mx or 0) > cut_active
            flag = ""
            if n >= HARD_EV or mb >= HARD_MB:
                flag = "硬阈"; hard.append((agent, sid, n, mb, active))
            elif n >= SOFT_EV or mb >= SOFT_MB:
                flag = "软阈"; soft.append((agent, sid, n, mb, active))
            if flag:
                lines.append("- [%s] %s / %s…  事件 %d  %.1f MB  %s" % (
                    flag, agent, sid[:12], n, mb, "（活动会话·只告警）" if active else ""))
    stamp = now().strftime("%Y%m%d")
    out = os.path.join(OUT_DIR, "session-hygiene-%s.md" % stamp)
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 会话体积巡检 %s\n\n" % now().strftime("%Y-%m-%d %H:%M"))
        f.write("阈值：软 %d 事件/%.0f MB，硬 %d 事件/%.0f MB\n\n" % (SOFT_EV, SOFT_MB, HARD_EV, HARD_MB))
        f.write("扫描 %d 个 agent 库，总事件 %d\n\n" % (len(dbs), total_ev))
        if hard: f.write("## 超硬阈 %d 项\n" % len(hard)); [f.write(l+"\n") for l in lines if "硬阈" in l]
        if soft: f.write("## 超软阈 %d 项\n" % len(soft)); [f.write(l+"\n") for l in lines if "软阈" in l]
        if not hard and not soft: f.write("全部会话正常，无告警。\n")
    print("报告:", out)
    print("硬阈 %d 项 / 软阈 %d 项 / 总事件 %d" % (len(hard), len(soft), total_ev))
    return 1 if hard else 0

if __name__ == "__main__":
    sys.exit(main())
