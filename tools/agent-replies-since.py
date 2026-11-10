#!/usr/bin/env python3
"""列出「自上次检查以来有回话」的管家 agent id（排除 main）。
用法: python3 agent-replies-since.py
输出: {"agents": ["tax", ...]}
状态: workspace/state/agent-reply-cursor.json（记录日志文件 + 字节偏移）
"""
import json, os, re, glob

STATE = "/home/openclaw/.openclaw/workspace/state/agent-reply-cursor.json"
LOGDIR = "/tmp/openclaw"
PAT = re.compile(r'dispatching to agent \(session=agent:([A-Za-z0-9_-]+):')
EXCLUDE = {"main"}

def newest_log():
    fs = glob.glob(os.path.join(LOGDIR, "openclaw-*.log"))
    return max(fs, key=os.path.getmtime) if fs else None

def main():
    f = newest_log()
    if not f:
        print(json.dumps({"agents": []})); return
    st = {}
    if os.path.exists(STATE):
        try:
            with open(STATE) as fh: st = json.load(fh)
        except Exception: pass
    size = os.path.getsize(f)
    offset = st.get("offset", 0) if st.get("file") == f else 0
    if not isinstance(offset, int) or offset < 0 or offset > size: offset = 0
    agents = []
    try:
        with open(f, "r", errors="replace") as fh:
            fh.seek(offset)
            for line in fh:
                for m in PAT.finditer(line):
                    a = m.group(1)
                    if a in EXCLUDE or a in agents: continue
                    agents.append(a)
    except Exception as e:
        print(json.dumps({"agents": [], "error": str(e)})); return
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    try:
        with open(STATE, "w") as fh:
            json.dump({"file": f, "offset": size}, fh)
    except Exception: pass
    print(json.dumps({"agents": agents}, ensure_ascii=False))

main()
