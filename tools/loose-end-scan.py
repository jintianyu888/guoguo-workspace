#!/usr/bin/env python3
"""扫出"尾巴"：报告/账本里甩给主公的待办或选择。"""
import json
import re
import sys

PAT = re.compile(r"(待主公|请主公|需主公|请确认|你来定|你说一句|补转上一条|待拍板|等你|请回复)")
paths = sys.argv[1:] or ["state/work/day-plan.md", "state/reports"]
hits = []
for p in paths:
    try:
        if p.endswith(".md"):
            for i, line in enumerate(open(p, encoding="utf-8"), 1):
                if PAT.search(line):
                    hits.append((p, i, line.strip()[:120]))
    except (FileNotFoundError, IsADirectoryError):
        pass
for h in hits:
    print("%s:%d  %s" % h)
print("共 %d 条尾巴" % len(hits))
