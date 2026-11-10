#!/usr/bin/env python3
"""weekend-clear.py —— 周末清账规则（2026-11-07 主公令）
规定：除「需要主公动手」(wait_user=1) 与「周期性/计分」外，所有任务必须在周日 23:00 前做完并核验。
  · paused/frozen 视为主公明确冻结，不计入
  · 计分/周期性任务 = grp 含 '计分' 或 kind in ('periodic','score') 或标题含 '周记分''周期'
用法：weekend-clear.py [--plan|--check] [--json]
"""
import argparse, datetime as dt, json, os, sqlite3, sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(W, "state/tasks/tasks.db")
EXEMPT_KIND = ("periodic", "score")

def load():
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute(
        "select no,title,status,kind,grp,wait_user,due_plan,eta_min,verify,pin_time from tasks "
        "where status not in ('done','cancelled')")]
    return rows

def classify(r):
    g = (r.get("grp") or "")
    k = (r.get("kind") or "")
    t = r.get("title") or ""
    if r.get("wait_user"):
        return "owner"          # 等主公动手
    if k in EXEMPT_KIND or "计分" in g or "周记分" in t or "周期" in t:
        return "periodic"       # 周期性/计分，豁免
    if r.get("status") == "paused":
        return "frozen"         # 主公冻结，豁免
    return "must"               # 周末必须清掉

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = load()
    must, owner, periodic, frozen = [], [], [], []
    for r in rows:
        {"must": must, "owner": owner, "periodic": periodic, "frozen": frozen}[classify(r)].append(r)

    now = dt.datetime.now()
    today = now.date()
    # 本周日 23:00 截止
    deadline = today + dt.timedelta(days=(6 - today.weekday()))
    deadline_dt = dt.datetime.combine(deadline, dt.time(23, 0))
    overdue = [r for r in must if (r["due_plan"] or "") and r["due_plan"][:16] < now.strftime("%Y-%m-%d %H:%M")]

    if a.json:
        print(json.dumps({"must": must, "owner": owner, "periodic": periodic,
                          "frozen": frozen, "deadline": deadline.isoformat()}, ensure_ascii=False))
        return 0

    lines = []
    lines.append("周末清账（截止 %s 23:00）" % deadline.strftime("%m-%d"))
    if must:
        total_min = sum(int(r.get("eta_min") or 30) for r in must)
        lines.append("· 必须做完 %d 项，合计约 %.1fh" % (len(must), total_min / 60))
        for r in must:
            flag = "" if r.get("verify") else "｜缺验收"
            lines.append("   - #%s %s（计划 %s%s）" % (r["no"], (r["title"] or "")[:30],
                                                   (r.get("due_plan") or "未排")[:16], flag))
    else:
        lines.append("· 必须做完 0 项 —— 已清空")
    if owner:
        lines.append("· 等主公动手 %d 项（不计入）：%s" % (len(owner), "、".join("#%s" % r["no"] for r in owner)))
    if periodic:
        lines.append("· 周期性/计分 %d 项（豁免）" % len(periodic))
    if frozen:
        lines.append("· 已冻结 %d 项（豁免）" % len(frozen))
    if overdue:
        lines.append("⚠ 逾期未清：%s" % "、".join("#%s" % r["no"] for r in overdue))

    violation = bool(must) and now.weekday() == 6 and now >= deadline_dt - dt.timedelta(hours=3)
    if a.check and violation:
        lines.insert(0, "VIOLATION 周日晚仍有 %d 项未清" % len(must))
    print("\n".join(lines))
    return 1 if (a.check and violation) else 0

if __name__ == "__main__":
    sys.exit(main())
