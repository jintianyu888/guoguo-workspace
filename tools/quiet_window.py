#!/usr/bin/env python3
"""quiet_window.py — 静默窗口判定（定时断网/维护时段，监控不报错）
默认：每天 04:00–05:00（局域网+互联网定时中断；2026-10-05 主公告知）
CLI 退出码：0=在窗口内（应静默）/ 1=不在窗口内
可 import：in_quiet_window() -> bool
配置：state/quiet-windows.json
"""
import json, os, sys, datetime

W = "/home/j/.openclaw/workspace"
CFG = os.path.join(W, "state", "quiet-windows.json")
DEFAULT = [{"start": "04:00", "end": "06:05", "note": "路由器 04:00 起重启，至约 06:00 恢复（2026-10-16 主公口径）"}]

def _load():
    try:
        with open(CFG, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("windows") or DEFAULT
    except Exception:
        return DEFAULT

def _tom(s):
    h, m = str(s).split(":")[:2]
    return int(h) * 60 + int(m)

def in_quiet_window(now=None):
    now = now or datetime.datetime.now()
    cur = now.hour * 60 + now.minute
    for w in _load():
        a, b = _tom(w.get("start", "04:00")), _tom(w.get("end", "06:05"))
        if a <= b:
            if a <= cur < b:
                return True
        else:
            if cur >= a or cur < b:
                return True
    return False

def main():
    print("quiet" if in_quiet_window() else "active")
    return 0 if in_quiet_window() else 1

if __name__ == "__main__":
    sys.exit(main())
