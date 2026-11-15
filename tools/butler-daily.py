#!/usr/bin/env python3
"""butler-daily.py — 五大管家今日自审状态（零 token）
输出: state/butler/today.json + 屏幕摘要
判定: cron 下次/上次运行时间 + 工作区 state/self-review/<今天>.md 是否存在
"""
import json, os, subprocess, datetime, glob, sys

W = "/home/j/.openclaw/workspace"
CLI = "/home/j/.npm-global/bin/openclaw"
OUT = os.path.join(W, "state", "butler", "today.json")
BUTLERS = [("maint", "维护"), ("backup", "备份"), ("model", "模型"), ("work", "干活"), ("sheet-music", "Hermess")]
WS = {
    "maint": "/home/j/openclaw-workspaces/maint",
    "backup": "/home/j/.openclaw/workspace-backup",
    "model": "/home/j/.openclaw/workspace-model",
    "work": "/home/j/openclaw-workspaces/work",
    "sheet-music": "/home/j/openclaw-workspaces/sheet-music",
}


def cron_jobs():
    try:
        r = subprocess.run([CLI, "cron", "list", "--json"], capture_output=True, text=True, timeout=120)
        return json.loads(r.stdout).get("jobs", [])
    except Exception:
        return []


def fmt(ms):
    if not ms:
        return ""
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%m-%d %H:%M")


def main():
    today = datetime.date.today().isoformat()
    jobs = {(j.get("effectiveAgentId") or j.get("agentId")): j for j in cron_jobs() if "自审" in (j.get("name") or "")}
    out = []
    for aid, name in BUTLERS:
        j = jobs.get(aid) or {}
        st = j.get("state") or {}
        ws = WS.get(aid, "")
        review_dir = os.path.join(ws, "state", "self-review") if ws else ""
        today_file = os.path.join(review_dir, today + ".md") if review_dir else ""
        for cand in (today + ".md", "self-review-" + today + ".md",
                     today.replace("-", "") + ".md", "self-review-" + today.replace("-", "") + ".md"):
            alt = os.path.join(review_dir, cand) if review_dir else ""
            if alt and os.path.exists(alt):
                today_file = alt
                break
        latest = ""
        if review_dir and os.path.isdir(review_dir):
            files = sorted(glob.glob(os.path.join(review_dir, "*.md")))
            if files:
                latest = os.path.basename(files[-1])
        out.append({
            "id": aid,
            "name": name,
            "job": j.get("name") or "",
            "next_run": fmt(st.get("nextRunAtMs")),
            "last_run": fmt(st.get("lastRunAtMs")),
            "last_status": st.get("lastRunStatus") or "",
            "job_enabled": bool(j.get("enabled")),
            "job_missing": not bool(j),
            "review_today": bool(today_file and os.path.exists(today_file)),
            "review_latest": latest,
            "review_size": os.path.getsize(today_file) if (today_file and os.path.exists(today_file)) else 0,
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"updated": datetime.datetime.now().strftime("%F %T"), "date": today, "butlers": out},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    missing = [b["name"] for b in out if not b["review_today"]]
    for b in out:
        print("%-9s 下次自审 %-11s 上次 %-11s %-3s 今日产出 %s" % (
            b["name"], b["next_run"] or "-", b["last_run"] or "-", b["last_status"] or "-",
            ("有(%dB)" % b["review_size"]) if b["review_today"] else ("无，最近 " + (b["review_latest"] or "从未"))))
    print("写入", OUT)
    if "--check" in sys.argv:
        if missing:
            print("MISSING:" + ",".join(missing))
            return 1
        print("ALL_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
