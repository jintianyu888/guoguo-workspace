#!/usr/bin/env python3
"""检测群晖投放箱 ~/openclaw-inbox/<管家>/ 是否有**新文件**（未处理）。
用法: python3 inbox-check.py
输出: {"pending": {"recipe-mystery": 2, ...}}  —— 每管家待处理文件数
状态: workspace/state/inbox-seen.json（记录已处理文件的 路径+大小+mtime）
"""
import json, os, subprocess

NAS = "nas"
STATE = os.path.expanduser("~/.openclaw/workspace/state/inbox-seen.json")
SSH = ["-o","BatchMode=yes","-o","ConnectTimeout=10","-o","StrictHostKeyChecking=accept-new"]

seen = {}
if os.path.exists(STATE):
    try: seen = json.load(open(STATE))
    except Exception: seen = {}

try:
    r = subprocess.run(["ssh", *SSH, NAS,
        "find ~/openclaw-inbox -mindepth 2 -type f -printf '%p|%s|%T@\\n' 2>/dev/null"],
        capture_output=True, text=True, timeout=120)
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
except Exception as e:
    print(json.dumps({"pending": {}, "error": type(e).__name__})); raise SystemExit

new_state, pending = {}, {}
for line in lines:
    parts = line.split("|")
    if len(parts) != 3: continue
    path, size, mt = parts[0], parts[1], parts[2]
    key = f"{path}|{size}|{mt}"
    new_state[path] = key
    if seen.get(path) != key:
        # 归属管家 = 第一层子目录
        rel = path.split("openclaw-inbox/", 1)[-1]
        aid = rel.split("/", 1)[0]
        pending[aid] = pending.get(aid, 0) + 1

json.dump(new_state, open(STATE, "w"), ensure_ascii=False)
print(json.dumps({"pending": pending}, ensure_ascii=False))
