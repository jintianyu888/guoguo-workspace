#!/usr/bin/env python3
"""tmp-audit.py — 找「没转正的临时脚本」（2026-11-20 主公令）

背景：飞书剪辑管家接入时发现 tools/_tmp_scopes2.js 早就跑通过，但因为叫 _tmp_ 没进技能，
下次又从零写一遍。这个脚本每周把临时件捞出来，逼着做二选一：转正 or 清理。

用法：python3 tools/tmp-audit.py [--days 30]
输出：state/work/tmp-audit.json + 屏幕清单
退出码：0 无 → 有临时件时打印清单（不失败，避免误红）
"""
import os, sys, json, time, glob

ROOTS = ["/home/j/.openclaw/workspace", "/home/j/openclaw-workspaces"]
SKIP = ("node_modules", "/.git/", "state/trash", "state/panelshots", "/media/", ".cache",
        "openclaw-backups", "state/backup", ".versions", "/memory/",
        "__pycache__", "-venv", "回收站", "site-packages", "onnxruntime")
# 只找「一次性脚本/草稿」类；.bak 是有意的回滚件，不算临时件
PATTERNS = ("_tmp_", "/tmp_", "scratch_", "demo_", "draft_")


def main():
    days = 30
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    cutoff = time.time() - days * 86400
    hits = []
    for root in ROOTS:
        for dp, dn, fn in os.walk(root):
            if any(s in dp for s in SKIP):
                continue
            for f in fn:
                low = f.lower()
                if not any(p in low for p in PATTERNS):
                    continue
                if os.path.splitext(f)[1].lower() not in (".py", ".js", ".sh", ".ts", ".md", ".cjs", ".mjs"):
                    continue
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if st.st_mtime < cutoff:
                    continue
                hits.append({"path": p, "size": st.st_size,
                             "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
    hits.sort(key=lambda h: h["mtime"], reverse=True)
    os.makedirs("/home/j/.openclaw/workspace/state/work", exist_ok=True)
    json.dump(hits, open("/home/j/.openclaw/workspace/state/work/tmp-audit.json", "w"), ensure_ascii=False, indent=1)
    print("近 %d 天临时件: %d 个" % (days, len(hits)))
    for h in hits[:40]:
        rel = h["path"].replace("/home/j/.openclaw/workspace/", "").replace("/home/j/openclaw-workspaces/", "WS:")
        print("  %s  %6.1fK  %s" % (h["mtime"], h["size"] / 1024, rel))
    if hits:
        print("→ 每个都得二选一：转正成正式工具/技能，或移进 state/trash/（不许长期躺 tools/）")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
