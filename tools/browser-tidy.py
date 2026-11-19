#!/usr/bin/env python3
"""browser-tidy.py v0.1 — 关闭重复标签页，每个站点只留一页（只关多余，不动控制面板）
用法：python3 tools/browser-tidy.py [--dry-run]
规则：
 - 按域名分组，每组保留一个：优先保留 PREFER 里的路径，否则保留最后一个
 - 永不关闭：无 URL 的页（控制面板/新标签）、127.0.0.1/localhost、标题含 OpenClaw
"""
import json, subprocess, sys
from urllib.parse import urlparse

PROFILE = "chrome"
PREFER = {
    "open.bigmodel.cn": "/coding-plan/personal/overview",
    "platform.deepseek.com": "/usage",
    "platform.kimi.com": "/console/account",
    "platform.minimax.cn": "/console/recharge-records",
}

def run(args, t=60):
    p = subprocess.run(["timeout", str(t), "openclaw", "browser"] + args + ["--browser-profile", PROFILE, "--json"],
                       capture_output=True, text=True, timeout=t + 10)
    return p.returncode, (p.stdout or "") + (p.stderr or "")

def tabs():
    rc, out = run(["tabs"])
    try:
        d = json.loads(out[out.index("{"):]) if "{" in out else {}
    except Exception:
        return []
    return d.get("tabs") or []

def main():
    dry = "--dry-run" in sys.argv
    ts = tabs()
    if not ts:
        print("tabs: 读取失败或为空"); return 1
    groups = {}
    for t in ts:
        url = t.get("url") or ""
        tid = t.get("tabId") or t.get("targetId")
        title = t.get("title") or ""
        if not url:
            print("保留(无URL):", tid, title[:24]); continue
        host = urlparse(url).hostname or ""
        if host in ("127.0.0.1", "localhost", "192.168.1.108") or "OpenClaw" in title:
            print("保留(控制面板):", tid, title[:24]); continue
        groups.setdefault(host, []).append(t)
    closed = 0
    for host, lst in groups.items():
        if len(lst) <= 1:
            continue
        pref = PREFER.get(host)
        keep = None
        if pref:
            for t in lst:
                if (t.get("url") or "").endswith(pref) or pref in (t.get("url") or ""):
                    keep = t; break
        if keep is None:
            keep = lst[-1]
        for t in lst:
            if t is keep:
                continue
            tid = t.get("tabId") or t.get("targetId")
            if dry:
                print("将关闭:", tid, host, (t.get("url") or "")[:60])
            else:
                rc, out = run(["close", str(tid)], 40)
                print("关闭:", tid, host, "rc=%s" % rc)
            closed += 1
        print("保留:", keep.get("tabId"), host, (keep.get("url") or "")[:60])
    print("共关闭 %d 个重复页%s" % (closed, "（dry-run）" if dry else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
