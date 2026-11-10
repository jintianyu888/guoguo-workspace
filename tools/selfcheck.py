#!/usr/bin/env python3
# selfcheck.py —— 果果·闲时零成本自查调度器（0 token）
# 方案：docs/自查方案.md
# 用法：
#   python3 tools/selfcheck.py --run [--limit N] [--only ID] [--force]
#   python3 tools/selfcheck.py --list
#   python3 tools/selfcheck.py --report
# 约定：干净 → 无输出（静默）；有异常 → 打印告警块（供 announce 投递）并追加 state/security-alerts.md
import argparse, datetime, json, os, re, subprocess, sys

W = "/home/j/.openclaw/workspace"
QUEUE = os.path.join(W, "state/selfcheck-queue.json")
REPORT = os.path.join(W, "state/selfcheck-report.json")
ALOG = os.path.join(W, "state/security-alerts.md")
PAUSE = os.path.join(W, "state/selfcheck-pause")   # 存在=暂停自查（忙时/维护）
ALERT_RE = re.compile(r"(🔴|❌|⚠️)")   # 只认强标记；个别项可用 item['alert_regex'] 覆盖

def nowiso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")

def nowhm():
    return datetime.datetime.now().strftime("%m-%d %H:%M")

def load():
    with open(QUEUE, encoding="utf-8") as f:
        return json.load(f)

def save(q):
    q["updated"] = nowiso()
    tmp = QUEUE + ".t"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QUEUE)

def run_one(it):
    cmd = it.get("cmd") or ""
    if not cmd:
        return {"id": it["id"], "name": it["name"], "dim": it.get("dim", ""),
                "result": "todo", "rc": None, "output": "（未接线：待二期补脚本）",
                "cause": "", "fix": "", "ts": nowiso()}
    try:
        p = subprocess.run(cmd, shell=True, cwd=W, capture_output=True, text=True,
                           timeout=int(it.get("timeout", 300)))
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        rc = p.returncode
    except subprocess.TimeoutExpired:
        out, rc = "TIMEOUT(>%ss)" % it.get("timeout", 300), 124
    except Exception as e:
        out, rc = "EXEC ERROR: %s" % e, 125
    rx = it.get("alert_regex")
    pat = re.compile(rx) if rx else ALERT_RE
    alert = (rc != 0) or bool(pat.search(out))
    return {"id": it["id"], "name": it["name"], "dim": it.get("dim", ""),
            "result": "alert" if alert else "ok", "rc": rc,
            "output": out[-1500:], "cause": it.get("cause", ""), "fix": it.get("fix", ""), "ts": nowiso()}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    # 静默窗口（定时断网时段）内不报错（2026-10-05 主公令）
    if not a.force:
        try:
            sys.path.insert(0, os.path.join(W, "tools"))
            from quiet_window import in_quiet_window
            if in_quiet_window():
                return 0
        except Exception:
            pass

    q = load()
    items = q.get("items", [])

    if a.list:
        for it in items:
            print("%-14s %-6s %-10s %s" % (it["id"], it.get("status", ""), it.get("dim", ""), it["name"]))
        return 0
    if a.report:
        print(open(REPORT, encoding="utf-8").read() if os.path.exists(REPORT) else "（暂无报告）")
        return 0
    if not a.run:
        ap.print_help()
        return 0

    if os.path.exists(PAUSE) and not a.force:
        return 0  # 忙时/维护：静默跳过

    pool = [it for it in items if it.get("status") != "todo" and it.get("cmd")]
    if a.only:
        pool = [it for it in items if it["id"] == a.only]
    pool.sort(key=lambda it: it.get("last_run") or "")
    picks = pool[:max(1, a.limit)]
    if not picks:
        return 0

    results = []
    for it in picks:
        r = run_one(it)
        it["last_run"] = nowiso()
        it["last_result"] = r["result"]
        it["runs"] = int(it.get("runs", 0)) + 1
        results.append(r)

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"ts": nowiso(), "results": results}, f, ensure_ascii=False, indent=1)
    save(q)

    alerts = [r for r in results if r["result"] == "alert"]
    if alerts:
        lines = ["🔎【闲时自查·发现异常】" + nowhm() + "（共 %d 项）" % len(alerts)]
        for r in alerts:
            lines.append("① 问题：%s（%s）" % (r["name"], r["dim"]))
            lines.append("② 原因：%s" % (r.get("cause") or "见下方原始输出"))
            lines.append("③ 怎么办：%s" % (r.get("fix") or "我会按性质自愈；需要你定的单独发"))
            if r["output"]:
                lines.append("   原始输出：" + r["output"].replace("\n", "\n   ")[:600])
        block = "\n".join(lines)
        print(block)
        try:
            with open(ALOG, "a", encoding="utf-8") as f:
                f.write("[%s] %s\n" % (datetime.datetime.now().strftime("%F %T"), block))
        except Exception:
            pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
