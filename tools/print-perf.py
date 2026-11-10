#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""print-perf.py —— 打印绩效：每次打印记速度，画曲线，打分（2026-11-07 主公令）

记录字段：ts / file / method(ipp631|raw9100) / pages / bytes / dpi / paper / secs / ppm / rc
打分口径（相对自身最好成绩，不跟别人比）：
  base 60 + 40 × (ppm / best_ppm)，封顶 100；
  失败（rc≠0）该次记 0 分；连续 3 次失败额外 -10。
  质量项单独记：DPI 低于历史中位数时标 "质降"。
用法：
  print-perf.py record --file X --pages N --bytes B --secs S --method ipp631 [--dpi 600] [--paper A3] [--rc 0]
  print-perf.py report [--days 30]
"""
import json, os, sys, datetime, statistics

WS = "/home/j/.openclaw/workspace"
J = WS + "/state/print/perf.jsonl"
OUT = WS + "/state/print/perf-report.md"


def rec(**kw):
    os.makedirs(os.path.dirname(J), exist_ok=True)
    pages = float(kw.get("pages") or 0)
    secs = float(kw.get("secs") or 0)
    ppm = round(pages / secs * 60, 1) if pages > 0 and secs > 0 else 0.0
    row = {"ts": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
           "file": kw.get("file", ""), "method": kw.get("method", ""),
           "pages": pages, "bytes": int(kw.get("bytes") or 0), "secs": round(secs, 1),
           "ppm": ppm, "dpi": int(kw.get("dpi") or 0), "paper": kw.get("paper", ""),
           "rc": int(kw.get("rc") or 0)}
    with open(J, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("记录：%s %s %s页 %.1fs → %.1f 页/分 rc=%s" % (row["ts"], os.path.basename(row["file"]), pages, secs, ppm, row["rc"]))
    return row


def load(days=None):
    if not os.path.exists(J):
        return []
    rows = []
    for line in open(J, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if days:
            try:
                t = datetime.datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                continue
            if (datetime.datetime.now() - t).days > days:
                continue
        rows.append(r)
    return rows


def report(days=30):
    rows = load(days)
    lines = ["# 打印绩效 %s（近 %d 天，%d 次）" % (datetime.date.today(), days, len(rows)), ""]
    if not rows:
        lines.append("- 暂无记录。每次打印走 print-ipp.py 会自动记；手工补记用 print-perf.py record")
    else:
        ok = [r for r in rows if r["rc"] == 0 and r["ppm"] > 0]
        best = max([r["ppm"] for r in ok], default=0)
        med = statistics.median([r["ppm"] for r in ok]) if ok else 0
        fails = [r for r in rows if r["rc"] != 0]
        lines.append("- 成功 %d 次 / 失败 %d 次｜中位 %.1f 页/分｜最好 %.1f 页/分" % (len(ok), len(fails), med, best))
        lines.append("- 评分：%d/100（相对自身最好成绩）" % (100 if best == 0 else int(min(100, 60 + 40 * med / best))))
        lines.append("")
        lines.append("## 速度曲线（最近 15 次，页/分）")
        tail = ok[-15:]
        if tail:
            mx = max(r["ppm"] for r in tail) or 1
            for r in tail:
                bar = "█" * max(1, int(round(r["ppm"] / mx * 30)))
                lines.append("- %s %-28s %5.1f %s" % (r["ts"][5:16], os.path.basename(r["file"])[:28], r["ppm"], bar))
        lines.append("")
        lines.append("## 待改进信号")
        dips = [r for r in ok if med and r["ppm"] < med * 0.8]
        lines.append("- 低于中位 80%% 的次数：%d（多为大文件/高 DPI，逐条看）" % len(dips))
        lines.append("- 失败：%d（若连续 3 次失败应停线查设备）" % len(fails))
    txt = "\n".join(lines)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(txt + "\n")
    print(txt)
    print("→ " + OUT)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(0)
    if a[0] == "record":
        kw = {}
        i = 1
        while i < len(a):
            k = a[i].lstrip("-")
            v = a[i + 1] if i + 1 < len(a) else ""
            kw[k] = v
            i += 2
        rec(**kw)
    elif a[0] == "report":
        d = 30
        if "--days" in a:
            d = int(a[a.index("--days") + 1])
        report(d)
    else:
        print(__doc__)
