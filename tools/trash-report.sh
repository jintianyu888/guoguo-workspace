#!/usr/bin/env bash
# 回收站报表 —— 输出总大小/文件数/按类型统计/最早最新条目（供日报）
set -euo pipefail

WS="/home/j/.openclaw/workspace"
TRASH="$WS/回收站"
MANIFEST="$TRASH/manifest.jsonl"
ITEMS="$TRASH/items"

python3 - "$TRASH" "$MANIFEST" "$ITEMS" <<'PY'
import json, os, sys, collections
trash, manifest, items = sys.argv[1:4]

def du(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try: total += os.path.getsize(os.path.join(root, f))
            except OSError: pass
    return total

size = du(trash)
recs = []
if os.path.exists(manifest):
    with open(manifest, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try: recs.append(json.loads(line))
                except Exception: pass

fcount = 0
if os.path.isdir(items):
    for root, _dirs, files in os.walk(items):
        fcount += len(files)

bytype = collections.Counter(r.get("类型", r.get("type", "?")) for r in recs)

def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n} B"

print(f"回收站总大小: {human(size)}（{size} 字节）")
print(f"条目数: {len(recs)} · 实际文件数: {fcount}")
print("按类型统计:")
for t in ("任务", "文件", "日程"):
    print(f"  {t}: {bytype.get(t, 0)}")
for t, c in sorted(bytype.items()):
    if t not in ("任务", "文件", "日程"):
        print(f"  {t}: {c}")
times = sorted(r.get("时间", "") for r in recs if r.get("时间"))
print(f"最早条目: {times[0] if times else '-'}")
print(f"最新条目: {times[-1] if times else '-'}")
PY
