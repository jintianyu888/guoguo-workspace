#!/usr/bin/env python3
# print-ledger-add.py —— 把「主会话直推」的打印登记进打印管家的同一本台账
# 2026-10-01 主公令：以后我的打印也走同一本台账，避免两条路互不知情导致重复
# 用法：print-ledger-add.py <文件> [备注]
import sys, os, json, time, hashlib, fcntl, re, datetime

JOBS = "/home/j/openclaw-workspaces/print/print/jobs.md"  # 2026-11-07 修正：旧 workspace-print 已废弃
SENT = "/home/j/.openclaw/workspace/state/print-sent.json"

def main():
    if len(sys.argv) < 2:
        print("用法: print-ledger-add.py <文件> [备注]"); return 2
    path = sys.argv[1]
    note = sys.argv[2] if len(sys.argv) > 2 else "果果直推（main agent）"
    if not os.path.isfile(path):
        print(f"❌ 文件不存在: {path}"); return 1
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    size = os.path.getsize(path)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        sent = json.load(open(SENT, encoding="utf-8"))
    except Exception:
        sent = {}
    dup = h in sent
    os.makedirs(os.path.dirname(JOBS), exist_ok=True)
    with open(JOBS, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0); txt = f.read()
        ids = [int(x) for x in re.findall(r"\|\s*#(\d+)\s*\|", txt)]
        n = (max(ids) if ids else 0) + 1
        f.seek(0, 2)
        f.write(f"| #{n} | {os.path.basename(path)}（{size} B） | A4×1 | 1 | 单面 | - | {now} | 打印中 | {note}；sha {h}；等出纸确认 |\n")
        fcntl.flock(f, fcntl.LOCK_UN)
    sent[h] = time.time()
    json.dump(sent, open(SENT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"✅ 已登记 #{n}（sha {h}）" + ("｜⚠️ 该内容此前打过，注意重复" if dup else ""))
    return 0

sys.exit(main())
