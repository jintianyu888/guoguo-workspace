#!/usr/bin/env python3
"""fake-green-scan.py —— 零 token 扫描"假绿"（按文件聚合，只报最值得看的）

判据（文件级）：未开 set -e/pipefail 且 吞错写法 >=3 处（|| true、>/dev/null 2>&1 无退出码判断），
或脚本结尾没有退出码传递。输出前 15 个文件，供人复核；不改任何文件。
"""
import os, re

ROOT = "/home/j/.openclaw/workspace/tools"
SKIP = (".bak", ".pyc", "__pycache__")
rows = []

for name in sorted(os.listdir(ROOT)):
    if not name.endswith((".sh", ".bash")):
        continue
    if any(s in name for s in SKIP):
        continue
    path = os.path.join(ROOT, name)
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    except Exception:
        continue
    head = "\n".join(lines[:10])
    has_errexit = bool(re.search(r"set -[a-z]*e|set -o errexit", head))
    swallow = 0
    sample = ""
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if s.startswith("#"):
            continue
        if s.endswith("|| true") or (">/dev/null 2>&1" in s and not re.search(r"\|\||if |&&", s)):
            swallow += 1
            if not sample:
                sample = "L%d %s" % (i, s[:60])
    tail = "\n".join(lines[-5:])
    no_exit = not re.search(r"exit [0-9$]|return [0-9$]", tail)
    if swallow >= 3 and (not has_errexit or no_exit):
        rows.append((swallow, os.path.basename(path), sample, has_errexit, no_exit))

rows.sort(key=lambda r: -r[0])
print("假绿扫描：值得复核 %d 个脚本（吞错 >=3 且无强退出码约束），列前 15" % len(rows))
for n, f, sample, er, ne in rows[:15]:
    flags = []
    if not er: flags.append("无set-e")
    if ne: flags.append("结尾不传退出码")
    print("- %-38s 吞错 %2d 处 [%s] %s" % (f, n, ",".join(flags), sample))
if not rows:
    print("未发现明显假绿写法")
