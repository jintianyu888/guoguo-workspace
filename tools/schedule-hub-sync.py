#!/usr/bin/env python3
"""日程中枢聚合：扫各管家工作区的 schedule-report.json → 合并去重 → 写 main 的 hub 文件。
只读其他管家工作区，只写 main 工作区。零 API 成本。
"""
import json, os, glob, datetime

BASE = "/home/openclaw/.openclaw"
WS = os.path.join(BASE, "workspace")
STATE = os.path.join(WS, "state")
FIELDS = ["agent", "事项", "日期", "时间", "提醒节奏", "状态", "备注"]


def load_items():
    rows = []
    for p in [os.path.join(WS, "schedule-report.json")] + sorted(glob.glob(os.path.join(BASE, "workspace-*", "schedule-report.json"))):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        agent = d.get("agent") or os.path.basename(os.path.dirname(p))
        for it in (d.get("items") or []):
            r = {"agent": agent}
            for f in FIELDS[1:]:
                r[f] = it.get(f, "")
            rows.append(r)
    return rows


def main():
    os.makedirs(STATE, exist_ok=True)
    rows = load_items()
    seen, out = set(), []
    for r in rows:
        k = (r["agent"], str(r.get("事项", "")), str(r.get("日期", "")))
        if k in seen:
            continue
        seen.add(k); out.append(r)
    out.sort(key=lambda r: (str(r.get("日期") or "9999"), str(r.get("agent"))))

    json.dump({"generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "count": len(out), "items": out},
              open(os.path.join(STATE, "schedule-hub.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    lines = ["# 日程中枢（全管家上报汇总）", "",
             f"> 生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M} · 共 {len(out)} 条", "",
             "| " + " | ".join(FIELDS) + " |",
             "|" + "---|" * len(FIELDS)]
    for r in out:
        lines.append("| " + " | ".join(str(r.get(f, "")) for f in FIELDS) + " |")
    open(os.path.join(STATE, "schedule-hub.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    agents = len({r["agent"] for r in out})
    print(f"聚合完成：{agents} 个管家 · {len(out)} 条事项 → state/schedule-hub.json|.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
