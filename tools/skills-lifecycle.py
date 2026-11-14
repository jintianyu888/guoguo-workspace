#!/usr/bin/env python3
"""skills-lifecycle.py —— 技能两段式生命周期 + 未沉淀候选捕获（零 token）

借鉴 Hermes Agent 的 curator / nudge 设计：
  - 生命周期：active → stale(14 天未用) → archived(30 天未用)，只归档不删除，pinned 豁免
  - 捕获：把近 N 天 worklog 里 deploy/change/fix/incident 且未被技能覆盖的条目，列成待沉淀候选

用法：
  python3 tools/skills-lifecycle.py curator [--apply]     # 计算状态；--apply 写回归档目录
  python3 tools/skills-lifecycle.py capture [--since 3]   # 生成待沉淀候选
  python3 tools/skills-lifecycle.py status
数据：state/skills/usage.jsonl（skill-usage.py 写入）、state/skills/pins.json、
      state/skills/lifecycle.json、state/skills/capture-queue.md
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta

WS = "/home/j/.openclaw/workspace"
SHARED = "/home/j/.openclaw/shared-skills"
ARCHIVE = "/home/j/.openclaw/shared-skills/.archived"
ST = os.path.join(WS, "state/skills")
USAGE = os.path.join(ST, "usage.jsonl")
PINS = os.path.join(ST, "pins.json")
LIFE = os.path.join(ST, "lifecycle.json")
QUEUE = os.path.join(ST, "capture-queue.md")
LOG = os.path.join(WS, "state/log/worklog.jsonl")
REG = os.path.join(ST, "registry.jsonl")

STALE_DAYS, ARCHIVE_DAYS = 14, 30
MAJOR = {"deploy", "change", "fix", "incident"}


def jl(p):
    out = []
    if not os.path.exists(p):
        return out
    for line in open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def jw(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def skills():
    d = {}
    if not os.path.isdir(SHARED):
        return d
    for n in sorted(os.listdir(SHARED)):
        p = os.path.join(SHARED, n, "SKILL.md")
        if os.path.exists(p):
            d[n] = {"path": os.path.join(SHARED, n), "mtime": os.path.getmtime(p)}
    return d


def last_used():
    lu = {}
    for e in jl(USAGE):
        s = e.get("skill") or e.get("name")
        ts = e.get("ts") or e.get("time") or ""
        if s:
            lu[s] = max(lu.get(s, ""), str(ts))
    return lu


def cmd_curator(apply):
    sk, lu = skills(), last_used()
    pins = set(json.load(open(PINS, encoding="utf-8"))) if os.path.exists(PINS) else set()
    now = datetime.now()
    rows, counts = [], {"active": 0, "stale": 0, "archived": 0, "pinned": 0}
    for name, meta in sk.items():
        if name in pins:
            counts["pinned"] += 1
            rows.append({"skill": name, "state": "pinned", "last_used": lu.get(name, "")})
            continue
        lu_ts = lu.get(name)
        base = datetime.fromisoformat(lu_ts) if lu_ts else datetime.fromtimestamp(meta["mtime"])
        age = (now - base).days
        state = "archived" if age >= ARCHIVE_DAYS else ("stale" if age >= STALE_DAYS else "active")
        counts[state] += 1
        rows.append({"skill": name, "state": state, "idle_days": age, "last_used": lu_ts or ""})
        if apply and state == "archived":
            os.makedirs(ARCHIVE, exist_ok=True)
            dst = os.path.join(ARCHIVE, name)
            if not os.path.exists(dst):
                shutil.move(meta["path"], dst)
                rows[-1]["moved_to"] = dst
    jw(LIFE, {"generated": now.isoformat(timespec="seconds"), "counts": counts, "skills": rows})
    print("技能 %d 个｜active %d / stale %d / archived %d / pinned %d%s" % (
        len(rows), counts["active"], counts["stale"], counts["archived"], counts["pinned"],
        "（已实际归档 %d 个到 .archived）" % counts["archived"] if apply else ""))
    for r in rows:
        if r["state"] == "stale":
            print("  ⚠️ 待优化(闲置 %s 天): %s" % (r.get("idle_days"), r["skill"]))
    return 0


def grams(text):
    t = "".join(ch for ch in str(text) if not ch.isspace())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def corpus():
    out = []
    for n, m in skills().items():
        try:
            out.append((n, grams(open(os.path.join(m["path"], "SKILL.md"), encoding="utf-8", errors="replace").read())))
        except Exception:
            pass
    return out


def cmd_capture(since):
    cutoff = (datetime.now() - timedelta(days=since)).isoformat()
    body = corpus()
    items, gaps = [], []
    for e in jl(LOG):
        if e.get("cat") not in MAJOR or str(e.get("ts", "")) < cutoff:
            continue
        items.append(e)
        if e.get("skill"):
            continue
        g = grams(str(e.get("target", "")) + str(e.get("evidence", ""))[:200])
        best = max((len(g & sg) / max(1, len(g | sg)) for _, sg in body), default=0)
        if len(str(e.get("target", ""))) >= 6 and best < 0.05:
            gaps.append((e.get("ts"), e.get("cat"), e.get("target"), best))
    os.makedirs(ST, exist_ok=True)
    with open(QUEUE, "w", encoding="utf-8") as f:
        f.write("# 待沉淀候选（%s 生成，近 %d 天）\n\n" % (datetime.now().isoformat(timespec="seconds"), since))
        f.write("成型成果 %d 条，疑似未沉淀 %d 条。\n\n" % (len(items), len(gaps)))
        for ts, cat, target, score in gaps[-40:]:
            f.write("- %s [%s] %s\n" % (ts, cat, target))
    print("近 %d 天成型成果 %d 条，疑似未沉淀 %d 条 → %s" % (since, len(items), len(gaps), QUEUE))
    return 0 if not gaps else 1


def cmd_status():
    if not os.path.exists(LIFE):
        print("尚未运行 curator")
        return 1
    d = json.load(open(LIFE, encoding="utf-8"))
    print("最近计算：%s" % d.get("generated"))
    print(json.dumps(d.get("counts", {}), ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("curator")
    c.add_argument("--apply", action="store_true")
    p = sub.add_parser("capture")
    p.add_argument("--since", type=int, default=3)
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "curator":
        return cmd_curator(a.apply)
    if a.cmd == "capture":
        return cmd_capture(a.since)
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())
