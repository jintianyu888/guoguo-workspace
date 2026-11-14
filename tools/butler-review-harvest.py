#!/usr/bin/env python3
"""butler-review-harvest.py — 从 cron 运行记录里收割管家自审正文，落盘到各自 state/self-review/
原因：维护管家等写工具被禁，报告只留在 cron run summary 里，等于没产出。"""
import json, os, subprocess, sys, datetime

JOBS = {
    "maint": ("aa6e71c3-fcf2-4119-9393-ad5ac4553889", "/home/j/openclaw-workspaces/maint"),
    "backup": ("123f03f2-2f3c-4987-ab86-00e5b83c8f64", "/home/j/.openclaw/workspace-backup"),
    "model": ("f2d7bf2f-2762-464c-87a2-74a22f765082", "/home/j/.openclaw/workspace-model"),
    "work": ("770cca92-b489-4326-8d9e-38ce9b3b0a6a", "/home/j/openclaw-workspaces/work"),
    "hermess": ("643ce055-43fc-4b06-8baa-deb53422f825", "/home/j/openclaw-workspaces/sheet-music"),
}
MIN_BYTES = 400

def runs(job_id):
    p = subprocess.run(["openclaw", "cron", "runs", job_id], capture_output=True, text=True, timeout=90)
    try:
        return json.loads(p.stdout).get("entries", [])
    except Exception:
        return []

def main():
    today = datetime.date.today().strftime("%Y-%m-%d")
    dry = "--dry" in sys.argv
    rc = 0
    for name, (jid, ws) in JOBS.items():
        d = os.path.join(ws, "state", "self-review")
        target = os.path.join(d, today + ".md")
        alt = os.path.join(d, today.replace("-", "") + ".md")
        if os.path.exists(alt) and os.path.getsize(alt) > MIN_BYTES:
            print("%-8s skip (已有 %s %dB)" % (name, os.path.basename(alt), os.path.getsize(alt)))
            continue
        if os.path.exists(target) and os.path.getsize(target) > MIN_BYTES:
            print("%-8s skip (已有 %dB)" % (name, os.path.getsize(target)))
            continue
        best = None
        for e in runs(jid):
            if e.get("action") != "finished":
                continue
            ts = e.get("tsIso") or ""
            if not ts.startswith(today):
                continue
            s = e.get("summary") or ""
            if len(s.encode()) >= MIN_BYTES and (best is None or len(s) > len(best)):
                best = s
        if not best:
            print("%-8s MISSING (今日无可用运行正文)" % name)
            rc = 1
            continue
        if dry:
            print("%-8s WOULD-WRITE %dB" % (name, len(best.encode())))
            continue
        os.makedirs(d, exist_ok=True)
        with open(target, "w") as f:
            f.write("# 每日自审 · %s · %s\n\n" % (name, today))
            f.write("> 来源：cron 运行记录 harvest（该管家无写权限时的兜底通道）\n\n")
            f.write(best)
            if not best.endswith("\n"):
                f.write("\n")
        print("%-8s wrote %s (%dB)" % (name, target, os.path.getsize(target)))
    return rc

if __name__ == "__main__":
    sys.exit(main())

