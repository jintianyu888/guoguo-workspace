#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管家交付验收 v1 —— 独立于网关启动闸，只扫文件与证据，不依赖 cron/网关。
用法: python3 tools/steward-acceptance.py [--send]
输出: state/self-review/acceptance-YYYYMMDD.md  (+ --send 时发飞书)
"""
import os, re, sys, json, datetime, subprocess

WS = "/home/j/.openclaw/workspace"
STEWARDS = {
    "维护管家(maint)":  ["/home/j/openclaw-workspaces/maint"],
    "干活管家(work)":   ["/home/j/openclaw-workspaces/work"],
    "备份管家(backup)": ["/home/j/.openclaw/workspace-backup"],
    "模型管家(model)":  ["/home/j/.openclaw/workspace-model"],
}
# 只读管家(maint)的交付走报告，不走自建文件
REPORT_GLOB = {
    "维护管家(maint)": [os.path.join(WS, "state/self-review/maint-%s.md")],
}
SKIP_DIR = {".git", "node_modules", "__pycache__", "inbox", ".cache", "venv", ".venv",
            "memory", ".dreams", "dreaming", "session-corpus", "sessions", ".obsidian"}
# 自我维护/身份类文件不算交付
SKIP_NAME = {"AGENTS.md", "IDENTITY.md", "SOUL.md", "MEMORY.md", "USER.md", "DREAMS.md",
             "BOOT.md", "HEARTBEAT.md", "TOOLS.md"}
SKIP_EXT = {".bak", ".log", ".pyc", ".tmp", ".swp", ".png", ".jpg", ".zip", ".gz", ".mp4", ".db"}
EVIDENCE = [
    re.compile(r"[A-Za-z0-9_./-]+\.(?:sh|py|md|json|js|conf|env):\d+"),
    re.compile(r"\brc\s*=\s*\d+", re.I),
    re.compile(r"exit\s*(?:code|状态)"),
    re.compile(r"\b[0-9a-f]{40,64}\b"),
    re.compile(r"(?:bash|python3|sqlite3|openclaw)\s+tools/"),
]
MAXREAD = 200_000

def scan(root, day_start):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR]
        depth = dirpath[len(root):].count(os.sep)
        if depth > 3:
            dirnames[:] = []
            continue
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_EXT:
                continue
            if fn in SKIP_NAME or fn.startswith("RULES-") or fn.startswith("PERM-"):
                continue
            if fn.startswith("2026-") and fn.endswith(".txt"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if not os.path.isfile(p) or st.st_size > 5_000_000:
                continue
            if st.st_mtime >= day_start:
                files.append((p, st.st_size))
    return files

def count_evidence(paths):
    hits = 0
    samples = []
    for p, sz in paths:
        if sz > MAXREAD:
            continue
        try:
            txt = open(p, "r", encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        n = 0
        for rx in EVIDENCE:
            for m in rx.finditer(txt):
                n += 1
                if len(samples) < 3:
                    line = txt[:m.start()].count("\n") + 1
                    samples.append("%s:%d" % (os.path.basename(p), line))
        hits += n
    return hits, samples[:3]

def main():
    today = datetime.date.today()
    day_start = datetime.datetime.combine(today, datetime.time(0, 0)).timestamp()
    lines = ["# 管家交付验收 · %s" % today.strftime("%Y-%m-%d"), ""]
    summary = []
    bad = 0
    for name, roots in STEWARDS.items():
        files = []
        for r in roots:
            if os.path.isdir(r):
                files += scan(r, day_start)
        for pat in REPORT_GLOB.get(name, []):
            p = pat % today.strftime("%Y-%m-%d")
            if os.path.isfile(p) and os.stat(p).st_mtime >= day_start:
                files.append((p, os.path.getsize(p)))
        ev, samples = count_evidence(files)
        if not files:
            verdict, mark = "未交（今日无任何产出文件）", "❌"
            bad += 1
        elif ev >= 3:
            verdict, mark = "已交，证据 %d 处" % ev, "✅"
        else:
            verdict, mark = "有文件但缺证据（%d 处）" % ev, "⚠️"
            bad += 1
        lines.append("%s **%s** — %s（今日 %d 个文件）" % (mark, name, verdict, len(files)))
        for p, _ in files[:4]:
            lines.append("   · %s" % p.replace(WS, "~ws"))
        if samples:
            lines.append("   证据样例：%s" % "、".join(samples))
        lines.append("")
        summary.append("%s %s：%s" % (mark, name.split("(")[0], verdict))
    lines.append("---")
    lines.append("判定口径：当日产出文件数 + 证据密度（file:line / rc= / exit code / 哈希 / 工具调用）。")
    lines.append("本检查不经过网关 cron，故不受启动自检闸影响。")
    outdir = os.path.join(WS, "state/self-review")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "acceptance-%s.md" % today.strftime("%Y%m%d"))
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(summary))
    print("报告: " + out)
    if "--send" in sys.argv:
        txt = "📋 管家交付验收 " + today.strftime("%m-%d") + "\n" + "\n".join(summary)
        if bad:
            txt += "\n⚠️ 有 %d 家不合格，详见 %s" % (bad, out)
        subprocess.run(["bash", os.path.join(WS, "tools/notify.sh"), txt], timeout=90)
    return 0

if __name__ == "__main__":
    sys.exit(main())
