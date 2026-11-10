#!/usr/bin/env python3
"""主会话上下文体量检测：超过阈值就建议压缩。
用法: python3 compact-if-large.py [--threshold 150000]
输出: {"compact": true/false, "tokens": N, "threshold": M}
"""
import argparse, json, subprocess
p = argparse.ArgumentParser()
p.add_argument("--threshold", type=int, default=150000)
a = p.parse_args()
tok = 0
try:
    r = subprocess.run(["openclaw","sessions","list","--agent","main","--json"],
                       capture_output=True, text=True, timeout=60)
    d = json.loads(r.stdout or "[]")
    s = d if isinstance(d, list) else d.get("sessions", [])
    for x in s:
        if x.get("key") == "agent:main:main":
            tok = x.get("inputTokens") or 0
            break
except Exception:
    tok = -1
print(json.dumps({"compact": tok > a.threshold, "tokens": tok, "threshold": a.threshold}))
