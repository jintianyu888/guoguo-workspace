#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""空转侦察 v1 —— 找出空转的管家 + 陈旧任务，产出待派清单。
不派单、不写台账，只出建议；派单由果果审后执行。
用法: python3 tools/idle-scout.py [--days 7]
"""
import os, re, sys, json, sqlite3, datetime, subprocess

WS = "/home/j/.openclaw/workspace"
LEDGER = os.path.join(WS, "state/ledger/ledger.db")
STEWARDS = {
    "maint": "/home/j/openclaw-workspaces/maint",
    "work": "/home/j/openclaw-workspaces/work",
    "backup": "/home/j/.openclaw/workspace-backup",
    "model": "/home/j/.openclaw/workspace-model",
}
SKIP_DIR = {"memory", ".dreams", ".git", "node_modules", "__pycache__", "inbox", "venv", ".venv", "sessions"}
SKIP_NAME = {"AGENTS.md", "IDENTITY.md", "SOUL.md", "MEMORY.md", "USER.md", "DREAMS.md", "BOOT.md"}
DOMAIN_HINT = {  # 陈旧任务按标题关键词归域
    "backup": ("备份", "盘", "保留", "回收站", "恢复", "drill", "NAS", "群晖", "镜像"),
    "model":  ("模型", "额度", "评审", "provider", "ollama", "评测", "token", "余额"),
    "maint":  ("告警", "巡检", "假绿", "监控", "体检", "日志", "stability", "告警"),
    "work":   ("脚本", "cron", "任务", "面板", "打印", "助手", "console", "定时"),
}

def age_days(p, today_start):
    try:
        return (today_start - os.stat(p).st_mtime) / 86400.0
    except OSError:
        return None

def todays_files(root, today_start):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIR]
        if dp[len(root):].count(os.sep) > 3:
            dns[:] = []
            continue
        for fn in fns:
            if fn in SKIP_NAME or fn.startswith(("RULES-", "PERM-")):
                continue
            if os.path.splitext(fn)[1].lower() in {".bak", ".log", ".pyc", ".png", ".jpg", ".db", ".gz"}:
                continue
            p = os.path.join(dp, fn)
            try:
                if os.path.isfile(p) and os.stat(p).st_mtime >= today_start:
                    out.append(p)
            except OSError:
                pass
    return out

def ledger_tasks():
    if not os.path.exists(LEDGER):
        return [], []
    c = sqlite3.connect(LEDGER)
    cur = c.cursor()
    cur.execute("SELECT task_id,title,status,assignee FROM tasks WHERE status IN ('pending','open','quarantine')")
    rows = cur.fetchall()
    cur.execute("SELECT task_id,title FROM tasks WHERE status='in_progress'")
    inprog = cur.fetchall()
    return rows, inprog

def classify(title):
    t = str(title)
    best, hits = None, 0
    for k, kws in DOMAIN_HINT.items():
        n = sum(1 for w in kws if w.lower() in t.lower())
        if n > hits:
            best, hits = k, n
    return best or "未归类"

def main():
    days = 7
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    today = datetime.date.today()
    tstart = datetime.datetime.combine(today, datetime.time(0, 0)).timestamp()
    rows, inprog = ledger_tasks()

    lines = ["# 空转侦察 · %s" % today.strftime("%Y-%m-%d"), ""]
    summary = []
    # 1) 谁在空转
    # 先自检：台账 assignee 里是否真有管家名，否则判定无效（防假绿）
    known = set(STEWARDS)
    assignees = {str(r[1] or "").strip().lower() for r in inprog}
    detectable = bool(assignees & known) or any(k in a for a in assignees for k in known)
    lines.append("## 一、空转判定")
    if not detectable:
        lines.append("⚠️ **无法判定**：台账 in_progress 的归属字段里没有管家名"
                     "（实际值：%s）。空转判定暂不可用，需先补归属字段。" % (sorted(assignees) or ["空"]))
        summary.append("空转判定:不可用(缺归属字段)")
        lines.append("")
    idle = []
    for name, root in (STEWARDS.items() if detectable else []):
        mine = [r for r in inprog if name in str(r[1] or "").lower()]
        files = todays_files(root, tstart) if os.path.isdir(root) else []
        # v0.4：文件产出不计入解除空转，只认在办任务与当日处置记录
        disp_today = os.path.join(WS, "state/work", "idle-dispose-%s.tsv" % today.strftime("%Y%m%d"))
        has_disp = os.path.exists(disp_today) and os.path.getsize(disp_today) > 200
        is_idle = (len(mine) == 0 and not has_disp)
        if is_idle:
            idle.append(name)
        lines.append("- %s 管家：在办 %d ｜ 今日产出 %d ｜ %s" % (
            name, len(mine), len(files), "⚠️ 空转" if is_idle else "在干活"))
        summary.append("%s:%s" % (name, "空转" if is_idle else "忙"))
    # 2) 陈旧任务
    lines.append("")
    lines.append("## 二、陈旧任务逐条销账表（共 %d 条，必须逐条填处置）" % len(rows))
    tsv = os.path.join(WS, "state/work", "idle-dispose-%s.tsv" % today.strftime("%Y%m%d"))
    with open(tsv, "w", encoding="utf-8") as f:
        f.write("task_id\tstatus\t域\t动作(认领/申请关闭/申请转派)\t证据\t标题\n")
        for tid, title, st, asg in rows:
            f.write("%s\t%s\t%s\t\t\t%s\n" % (tid, st, classify(title), str(title)[:80]))
    lines.append("销账表（可直接填）：%s" % tsv)
    lines.append("")
    groups = {}
    for tid, title, st, asg in rows:
        groups.setdefault(classify(title), []).append((tid, title, st, asg))
    for dom in sorted(groups, key=lambda k: -len(groups[k])):
        lines.append("### %s（%d 条）" % (dom, len(groups[dom])))
        for tid, title, st, asg in groups[dom][:12]:
            lines.append("- [%s] %s" % (st, str(title)[:70]))
        if len(groups[dom]) > 12:
            lines.append("- ……另 %d 条" % (len(groups[dom]) - 12))
        lines.append("")
    # 3) 建议
    if idle:
        lines.append("## 三、建议动作")
        for name in idle:
            cand = groups.get(name, [])
            lines.append("- %s 管家空转：优先认领本域陈旧任务 %d 条；若已清空，按线索清单找新任务（上限 5 条，入 quarantine）" % (name, len(cand)))
    else:
        lines.append("## 三、建议动作")
        lines.append("- 无管家空转，本次不触发找活")
    out = os.path.join(WS, "state/work", "idle-scout-%s.md" % today.strftime("%Y%m%d"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(" | ".join(summary))
    print("未完成任务 %d 条；报告 %s" % (len(rows), out))
    return 0

if __name__ == "__main__":
    sys.exit(main())
