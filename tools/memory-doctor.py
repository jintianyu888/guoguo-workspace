#!/usr/bin/env python3
"""记忆体检（只读）：查路径失效、重复条目、体积超限、过期索引。"""
import os, re, sys, collections, datetime

W = os.path.expanduser("~/.openclaw/workspace")
FILES = ["MEMORY.md", "AGENTS.md", "USER.md", "IDENTITY.md", "SOUL.md"]
SOFT = 12 * 1024

def read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()

def main():
    issues = []
    print("== 体积 ==")
    for f in FILES:
        p = os.path.join(W, f)
        if not os.path.exists(p):
            print(f"  {f}: 缺失"); issues.append((f, "缺失")); continue
        b = os.path.getsize(p)
        flag = "⚠️ 超 12KB" if b > SOFT else "ok"
        print(f"  {f}: {b} 字节 {flag}")
        if b > SOFT:
            issues.append((f, f"{b}B 超软限 {SOFT}B"))

    print("\n== 路径失效 ==")
    pat = re.compile(r"(/home/j/[\w\-./]+|tools/[\w\-]+\.(?:py|sh|md)|docs/[\w\-\u4e00-\u9fff]+\.(?:md|sh|py)|state/[\w\-./]+\.(?:jsonl|json|md))(?![\w])")
    bad = 0
    for f in FILES:
        p = os.path.join(W, f)
        if not os.path.exists(p): continue
        for i, line in enumerate(read(p).splitlines(), 1):
            for m in pat.findall(line):
                cand = [m] if m.startswith("/") else [os.path.join(W, m)]
                if not any(os.path.exists(c) for c in cand):
                    print(f"  {f}:{i} ✗ {m}")
                    bad += 1
                    if bad <= 40: issues.append((f"{f}:{i}", f"路径不存在 {m}"))
    print(f"  合计 {bad} 处")

    print("\n== 重复/矛盾线索 ==")
    seen = collections.defaultdict(list)
    for f in FILES:
        p = os.path.join(W, f)
        if not os.path.exists(p): continue
        for i, line in enumerate(read(p).splitlines(), 1):
            s = line.strip()
            if len(s) > 25 and not s.startswith(("|", "#")):
                seen[s].append(f"{f}:{i}")
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    for k, v in list(dup.items())[:15]:
        print(f"  重复: {v} :: {k[:70]}")
    print(f"  合计 {len(dup)} 组")

    print("\n== 同键不同值（疑似错乱）==")
    keypat = re.compile(r"^(\s*[-*]?\s*)([A-Za-z_\u4e00-\u9fff]{2,20})\s*[=:：]\s*(.+)$")
    kv = collections.defaultdict(set)
    for f in FILES:
        p = os.path.join(W, f)
        if not os.path.exists(p): continue
        for line in read(p).splitlines():
            m = keypat.match(line)
            if m and len(m.group(2)) <= 12:
                kv[m.group(2)].add(m.group(3).strip()[:60])
    conflicts = {k: v for k, v in kv.items() if len(v) > 1 and k.lower() not in ("时间", "备注")}
    for k, v in list(conflicts.items())[:12]:
        print(f"  {k}: {sorted(v)}")
    print(f"  合计 {len(conflicts)} 组")

    print("\n== 汇总 ==")
    print(f"  问题条目 {len(issues)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
