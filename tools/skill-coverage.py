#!/usr/bin/env python3
"""skill-coverage.py — 检查近期「成型成果」是否已沉淀成技能（零 token）

规则：最近 N 天 worklog 里 cat 属于 deploy/change/fix/incident 的条目，
若同一天有已发布技能（shared-skills）的 updated 时间或状态登记命中，则视为已沉淀；
否则列为「待沉淀」。可用 --since 天数，--json 输出。
"""
import argparse, json, os, sys, time
from datetime import datetime, timedelta

WS = "/home/j/.openclaw/workspace"
LOG = os.path.join(WS, "state/log/worklog.jsonl")
REG = os.path.join(WS, "state/skills/registry.jsonl")
SHARED = "/home/j/.openclaw/shared-skills"
MAJOR = {"deploy", "change", "fix", "incident"}


def load_jsonl(p):
    out = []
    if not os.path.exists(p):
        return out
    with open(p, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def skill_dates():
    """返回 {技能名: 最近更新时间戳}"""
    d = {}
    for e in load_jsonl(REG):
        name = e.get("name") or e.get("skill")
        ts = e.get("ts") or e.get("time") or ""
        if not name:
            continue
        try:
            t = datetime.fromisoformat(ts.replace("Z", "")).timestamp()
        except Exception:
            t = 0
        d[name] = max(d.get(name, 0), t)
    if os.path.isdir(SHARED):
        for n in os.listdir(SHARED):
            p = os.path.join(SHARED, n, "SKILL.md")
            if os.path.exists(p):
                ts = os.path.getmtime(p)
                d[n] = max(d.get(n, 0), ts)
    return d



STOP = set("的 了 和 与 加 上 下 一 个 中 为 在 是 有 无 不 断 建立 新增 完成 接入" .split())


def grams(text):
    t = "".join(ch for ch in str(text) if not ch.isspace())
    return {t[i:i + 2] for i in range(len(t) - 1)} - STOP


def skill_corpus():
    bag = []
    if os.path.isdir(SHARED):
        for n in os.listdir(SHARED):
            p = os.path.join(SHARED, n, "SKILL.md")
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8", errors="replace") as f:
                        bag.append((n, grams(f.read())))
                except Exception:
                    pass
    return bag


def covered(entry, corpus, th=0.05):
    if entry.get("skill"):
        return True, entry["skill"]
    g = grams(str(entry.get("target", "")) + str(entry.get("evidence", ""))[:200])
    if not g:
        return False, None
    best, bestj = None, 0.0
    for name, sg in corpus:
        if not sg:
            continue
        j = len(g & sg) / len(g | sg)
        if j > bestj:
            best, bestj = name, j
    return (bestj >= th), best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    cutoff = (datetime.now() - timedelta(days=a.since)).isoformat()
    sd = skill_dates()
    recent_skill = [k for k, v in sd.items() if v and datetime.fromtimestamp(v).isoformat() >= cutoff]
    items = [e for e in load_jsonl(LOG)
             if e.get("cat") in MAJOR and str(e.get("ts", "")) >= cutoff]
    # 粗判：同一自然日内有技能落地，即视为已沉淀（精细化交给人工确认）
    corpus = skill_corpus()
    gaps = []
    hit = 0
    for e in items:
        ok, who = covered(e, corpus)
        if ok:
            hit += 1
        else:
            e["_best"] = who
            gaps.append(e)
    if a.json:
        print(json.dumps({"since": a.since, "major_entries": len(items),
                          "recent_skills": sorted(recent_skill),
                          "covered": hit, "gaps": [{"ts": e.get("ts"), "cat": e.get("cat"), "target": e.get("target")} for e in gaps]},
                         ensure_ascii=False, indent=2))
        return 0 if not gaps else 1
    print("近 %d 天成型成果（deploy/change/fix/incident）：%d 条" % (a.since, len(items)))
    print("已判定被技能覆盖：%d 条 / 疑似未沉淀：%d 条" % (hit, len(gaps)))
    if not gaps:
        print("结论：✅ 无明显缺口")
        return 0
    print("⚠️ 疑似未沉淀（当天没有任何技能落地）：")
    for e in gaps[:20]:
        print("  - %s %s %s" % (e.get("ts"), e.get("cat"), e.get("target")))
    return 1


if __name__ == "__main__":
    sys.exit(main())
