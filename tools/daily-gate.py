#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daily-gate.py v1.0 — 开工前统一账本闸门（零 token）
一处聚合：我的任务 / 五大管家今日自审 / 执行账本收口 / 调度审计(变更触发)
/ 待主公决策 / 经验入口 / 我的每日固定动作稽核。
用法: python3 tools/daily-gate.py [--write]
输出: 屏幕 + state/work/daily-gate.json + docs/开工清单-YYYY-MM-DD.md
"""
import argparse, hashlib, json, os, subprocess, sys, time
from datetime import datetime, date

W = "/home/j/.openclaw/workspace"
OUTJSON = os.path.join(W, "state/work/daily-gate.json")
FP = os.path.join(W, "state/work/schedule-fingerprint.txt")
CLI = "/home/j/.npm-global/bin/openclaw"
now = datetime.now()
today = now.strftime("%Y-%m-%d")


def run(cmd, timeout=180):
    try:
        p = subprocess.run(cmd, shell=True, cwd=W, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return "ERR %s" % e


def sec_tasks():
    out = run("python3 tools/tasks-db.py list")
    rows = [l.rstrip() for l in out.splitlines() if l.strip().startswith("#")]
    return [l for l in rows if "[pending" in l or "[in_progress" in l]


def sec_butlers():
    run("python3 tools/butler-daily.py", 240)
    try:
        d = json.load(open(os.path.join(W, "state/butler/today.json")))
    except Exception:
        return {"updated": "?", "rows": [], "stale": True}
    rows = []
    for b in d.get("butlers", []):
        if b.get("review_today"):
            st = "已自审"
        elif b.get("job_missing") or not b.get("job_enabled"):
            st = "任务未启用"
        else:
            st = "未自审"
        note = (b.get("last_status") or "无状态") + (" 上次 " + (b.get("last_run") or "")[:16] if b.get("last_run") else "")
        rows.append({"name": b.get("name") or b.get("id"), "status": st, "note": note[:52]})
    upd = d.get("updated") or d.get("date") or "?"
    stale = today not in str(upd)
    return {"updated": upd, "rows": rows, "stale": stale}


def sec_exec():
    out = run("python3 tools/exec-ledger.py list -n 200")
    tail = [l for l in out.splitlines() if "合计" in l]
    today_rows = [l for l in out.splitlines() if l.strip().startswith(tuple("0123456789")) and today in l]
    bad = [l for l in today_rows if " fail " in l or " partial " in l]
    return {"total": tail[-1].strip() if tail else "?", "today": len(today_rows), "today_bad": bad[:3]}


def cron_fp():
    raw = run(CLI + " cron list --json", 240)
    try:
        data = json.loads(raw[raw.find("{"):] if "{" in raw else "[]")
        jobs = data.get("jobs", data if isinstance(data, list) else [])
    except Exception:
        jobs = []
    items = sorted("%s|%s|%s" % (j.get("id", ""), (j.get("schedule") or {}).get("expr", ""), j.get("enabled")) for j in jobs)
    return hashlib.sha256("\n".join(items).encode()).hexdigest()[:16], len(items)


def sec_sched():
    fp, n = cron_fp()
    old = open(FP).read().strip() if os.path.exists(FP) else ""
    changed = (old != fp)
    if changed:
        run("python3 tools/schedule-plan.py sync", 300)
    out = run("python3 tools/schedule-plan.py overlaps", 200)
    ov = "0"
    for l in out.splitlines():
        if "合计" in l:
            ov = l.strip()
    if changed:
        open(FP, "w").write(fp + "\n")
    return {"jobs": n, "fingerprint": fp, "changed": changed, "overlap": ov}


def sec_paused():
    out = run("python3 tools/tasks-db.py list")
    return [l.rstrip() for l in out.splitlines() if "[paused" in l]


DAILY_MINE = [
    ("07:20", "自我改进量化"),
    ("08:35", "开工闸门（本工具）"),
    ("08:50", "全栈体检 oc-doctor"),
    ("13:10", "午后简报"),
    ("18:05", "管家空转判定"),
    ("20:30", "晚间简报"),
    ("22:15", "技能候选捕获"),
    ("23:10", "执行账本渲染"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    tasks = sec_tasks()
    but = sec_butlers()
    ex = sec_exec()
    sch = sec_sched()
    paused = sec_paused()

    L = []
    L.append("▍开工清单 %s %s" % (today, now.strftime("%H:%M")))
    L.append("")
    L.append("一、我的在办（上限 6，当前 %d）%s" % (len(tasks), "  ⚠ 超限，先收口" if len(tasks) > 6 else ""))
    L += ["  " + t for t in tasks[:10]] or ["  （无）"]
    L.append("")
    L.append("二、五大管家今日自审（更新 %s%s）" % (but["updated"], "  ⚠ 非今日" if but["stale"] else ""))
    L += ["  %-8s %-6s %s" % (r["name"], r["status"], r["note"]) for r in but["rows"][:8]] or ["  （无数据）"]
    L.append("")
    L.append("三、执行账本：今日 %d 条%s" % (ex["today"], "，失败 %d" % len(ex["today_bad"]) if ex["today_bad"] else ""))
    L.append("  " + ex["total"])
    L.append("")
    L.append("四、调度审计：%d 个任务，%s" % (sch["jobs"], "⚠ 有变更→已重扫，请核对" if sch["changed"] else "无变更（沿用上次审计）"))
    L.append("  " + sch["overlap"])
    L.append("")
    L.append("五、待主公决策 %d 条" % len(paused))
    L += ["  " + p[:90] for p in paused[:5]]
    L.append("")
    L.append("六、开工前必查：python3 tools/exp.py <关键词> ｜ bash tools/skills-sync.sh")
    L.append("")
    L.append("七、规矩稽核 + 技能可用性")
    rc = run("python3 tools/rules-check.py")
    L += ["  " + l for l in rc.splitlines()]
    sd = run("python3 tools/skill-deps.py --need | tail -1")
    L.append("  " + (sd.strip() or "技能体检：无输出"))
    if len([l for l in rc.splitlines() if "❌" in l or "⚠" in l]):
        L.append("  修技能与权限：bash tools/skill-new.sh（新建）/ python3 tools/skill-deps.py --agent <id>（查缺口）")
    L.append("")
    L.append("八、我的每日固定动作")
    L += ["  %s  %s" % (t, n) for t, n in DAILY_MINE]

    text = "\n".join(L)
    print(text)
    if a.write:
        json.dump({"date": today, "tasks": tasks, "butlers": but, "exec": ex, "schedule": sch, "paused": paused},
                  open(OUTJSON, "w"), ensure_ascii=False, indent=1)
        with open(os.path.join(W, "docs/开工清单-%s.md" % today), "w") as f:
            f.write("# 开工清单 %s\n\n" % today + text + "\n")
        import shutil, os as _os
        _os.makedirs(os.path.join(W, "state/reports"), exist_ok=True)
        try:
            shutil.copyfile(os.path.join(W, "docs/开工清单-%s.md" % today), os.path.join(W, "state/reports/draft.md"))
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
