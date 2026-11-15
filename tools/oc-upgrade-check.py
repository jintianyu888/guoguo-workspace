#!/usr/bin/env python3
"""oc-upgrade-check.py —— OpenClaw 升级节奏检查（零 token，读 npm 元数据）

历史规律（2026-01 至 11-11 实测 132 个稳定版）：
  · 每 25~37 天开一条新功能线（x.y.1 为功能版，发布说明体量大 3~5 倍）
  · 同线补丁中位间隔 53.5 小时（约 2.2 天），首 2 周内出 60~75% 的补丁
  · 旧线继续收安全补丁约 2 个月（dist-tag: extended-stable）
策略：不追每个补丁；一条线只升一次，取「首版后 7~10 天的最高补丁版」，
      并要求该版已静默 >= SOAK_DAYS 天；beta/rc 永不升级。

用法：python3 tools/oc-upgrade-check.py [--soak 7] [--json]
"""
import argparse, json, subprocess, sys, urllib.request
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
REG = "https://registry.npmmirror.com/openclaw"


def installed():
    try:
        out = subprocess.run(["openclaw", "--version"], capture_output=True, text=True, timeout=30).stdout
        for tok in out.replace("(", " ").split():
            if tok[:2] == "20" and tok.count(".") >= 2:
                return tok.strip()
    except Exception:
        pass
    return "unknown"


def fetch():
    req = urllib.request.Request(REG, headers={"Accept": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=40))
    return d.get("time", {}), d.get("dist-tags", {})


def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--soak", type=int, default=7, help="要求静默天数")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    times, tags = fetch()
    rel = {k: dt(v) for k, v in times.items() if k not in ("created", "modified")}
    stable = sorted([(k, d) for k, d in rel.items() if "beta" not in k and "rc" not in k], key=lambda x: x[1])
    now = datetime.now(TZ)
    cur = installed()
    latest = tags.get("latest", "?")
    ext = tags.get("extended-stable", "?")
    line = ".".join(latest.split(".")[:2])
    patches = [(v, d) for v, d in stable if v.startswith(line + ".")]
    first = patches[0][1] if patches else None
    newest = patches[-1] if patches else (latest, rel.get(latest, now))
    age = (now - newest[1]).total_seconds() / 86400
    inline = (now - first).total_seconds() / 86400 if first else 0
    beta = tags.get("beta", "")
    verdict, why = "", []
    if cur == "unknown":
        verdict = "unknown"; why.append("读不到当前安装版本")
    elif cur == latest:
        if age < a.soak:
            verdict = "hold"
            why.append("已是最新稳定版 %s，但只发布 %.1f 天（要求静默 %d 天），先不动" % (latest, age, a.soak))
        else:
            verdict = "ok-stable"
            why.append("已在最新稳定版 %s，且已静默 %.1f 天" % (latest, age))
    else:
        if age >= a.soak and inline >= 7:
            verdict = "upgrade"
            why.append("目标版本 %s 已静默 %.1f 天、本线第 %.0f 天，符合策略" % (latest, age, inline))
            why.append("当前 %s → 目标 %s" % (cur, latest))
        else:
            verdict = "wait"
            why.append("最新稳定版 %s 才 %.1f 天、本线第 %.0f 天，未达静默 %d 天" % (latest, age, inline, a.soak))
            if beta:
                why.append("beta 频道为 %s：说明该线仍在打补丁，等它转稳定并静默后再升" % beta)
    out = {
        "installed": cur, "latest": latest, "extended_stable": ext,
        "line": line, "line_versions": [v for v, _ in patches],
        "latest_age_days": round(age, 1), "line_age_days": round(inline, 1),
        "soak_days": a.soak, "verdict": verdict, "reasons": why,
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("当前安装：%s｜latest：%s（%.1f 天前）｜extended-stable：%s" % (cur, latest, age, ext))
        print("当前线 %s 共 %d 版，已走 %.0f 天：%s" % (line, len(patches), inline, " ".join(v.split(".")[-1] for v, _ in patches)))
        print("结论：%s" % verdict)
        for w in why:
            print("  ·", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
