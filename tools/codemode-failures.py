#!/usr/bin/env python3
"""codemode-failures.py - Code Mode 失败分类诊断（零 token）

用途：区分「Code Mode 桥传输坏了」「guest 脚本自己报错」「工具/入参报错」。
日志里四种都写成 "Code Mode execution failed"，看不出差别；本脚本按
failurePhase / failureCode 分类，读 ~/.openclaw/logs/openclaw-YYYY-MM-DD.log。

分类口径：
  tool       failureCode=tool_error           底层工具返回错误（桥正常）
  args       failureCode=input_contract/invalid_input  调用参数不合规
  guest      failurePhase=input|guest          guest 脚本自身异常（JS 报错）
  transport  failurePhase=bridge|host 且无 code 真正的桥/宿主传输失败

用法：
  python3 tools/codemode-failures.py                 # 近 1 天
  python3 tools/codemode-failures.py --days 7
  python3 tools/codemode-failures.py --json
  python3 tools/codemode-failures.py --fail-on-transport   # 有传输失败 rc=1

退出码：0 = 无桥传输失败；1 = 存在桥传输失败或参数错误。
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

LOG_DIR = os.path.expanduser("~/.openclaw/logs")
ARG_CODES = {"input_contract", "invalid_input"}


def bucket(rec):
    code, phase = rec["code"], rec["phase"]
    if code == "tool_error":
        return "tool"
    if code in ARG_CODES:
        return "args"
    if phase in ("input", "guest"):
        return "guest"
    if phase in ("bridge", "host"):
        return "transport"
    return "guest" if code is None else "args"


def parse_record(line):
    if "Code Mode execution failed" not in line:
        return None
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        return None
    inner = d.get("1")
    if isinstance(inner, str):
        try:
            inner = json.loads(inner)
        except json.JSONDecodeError:
            inner = {}
    if not isinstance(inner, dict):
        inner = {}
    return {
        "ts": (d.get("time") or "")[:19],
        "session": inner.get("sessionKey", ""),
        "phase": inner.get("failurePhase"),
        "code": inner.get("failureCode"),
        "method": inner.get("bridgeMethod"),
        "category": inner.get("errorCategory"),
    }


def collect(days):
    rows = []
    today = datetime.now()
    for i in range(days):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        path = os.path.join(LOG_DIR, f"openclaw-{day}.log")
        if not os.path.exists(path):
            continue
        with open(path, errors="replace") as fh:
            for line in fh:
                rec = parse_record(line)
                if rec:
                    rec["bucket"] = bucket(rec)
                    rows.append(rec)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-transport", "--fail-on-bridge", dest="fail_on_transport", action="store_true")
    args = ap.parse_args()

    rows = collect(max(1, args.days))
    totals = Counter(r["bucket"] for r in rows)
    by_day = defaultdict(Counter)
    for r in rows:
        by_day[r["ts"][:10] or "unknown"][r["bucket"]] += 1

    if args.json:
        print(json.dumps({
            "days": args.days,
            "total": len(rows),
            "buckets": dict(totals),
            "by_day": {d: dict(c) for d, c in sorted(by_day.items())},
            "sessions": dict(Counter(r["session"] for r in rows).most_common(10)),
            "verdict": "ok" if totals["transport"] == 0 else "transport_broken",
        }, ensure_ascii=False, indent=2))
    else:
        print(f"== Code Mode 失败分类（近 {args.days} 天）")
        print(f"总数 {len(rows)}｜工具错 {totals['tool']}｜入参错 {totals['args']}｜guest 脚本错 {totals['guest']}｜桥传输错 {totals['transport']}")
        for day in sorted(by_day):
            c = by_day[day]
            print(f"  {day}  总 {sum(c.values())}  工具 {c['tool']}  入参 {c['args']}  guest {c['guest']}  传输 {c['transport']}")
        if rows:
            print("高频会话：")
            for ses, n in Counter(r["session"] for r in rows).most_common(5):
                print(f"  {n:3d}  {ses or '(无)'}")
        print("判定：" + ("桥正常，无传输失败" if totals["transport"] == 0 else f"存在 {totals['transport']} 次桥/宿主传输失败，需要修桥"))

    if args.fail_on_transport and totals["transport"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
