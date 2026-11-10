#!/usr/bin/env python3
"""统一体检日报: 汇总各类信号 -> 一页 markdown + 一条飞书"""
import json, os, re, subprocess, time, datetime, hashlib

W = "/home/j/.openclaw/workspace"
ST = os.path.join(W, "state")
AUD = os.path.join(ST, "audit")
os.makedirs(AUD, exist_ok=True)
NOW = datetime.datetime.now()
NOTIFY = os.path.join(W, "tools", "notify.sh")

def load(p, d=None):
    try:
        with open(p, errors="replace") as f:
            return json.load(f)
    except Exception:
        return d

def tail_err(path, hours=24):
    cut = time.time() - hours * 3600
    out = []
    try:
        with open(path, errors="replace") as f:
            lines = f.readlines()[-3000:]
    except Exception:
        return out
    for line in lines:
        m = re.match(r"(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)", line)
        if not m:
            continue
        try:
            ts = datetime.datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            continue
        if ts >= cut and re.search(r"ERROR|FAIL|异常|失败|错误|WARN", line):
            out.append(line.strip()[:160])
    return out

def forecast():
    try:
        rows = [l.split() for l in open(os.path.join(ST, "disk-history.log")).read().strip().splitlines()[-30:]]
    except Exception:
        return None
    pts = [(datetime.date.fromisoformat(r[0]), int(r[1])) for r in rows if len(r) >= 2 and r[0][:4].isdigit()]
    pts = sorted(dict(pts).items())
    if len(pts) < 3:
        return None
    (d0, p0), (d1, p1) = pts[0], pts[-1]
    days = (d1 - d0).days or 1
    rate = (p1 - p0) / days
    if rate <= 0.05:
        return {"rate": round(rate, 3), "days_left": None}
    return {"rate": round(rate, 3), "days_left": int((90 - p1) / rate)}

def main():
    col = load(os.path.join(AUD, "collect.json"), {}) or {}
    items = []

    def add(sev, cat, msg, fp=None):
        items.append({"sev": sev, "cat": cat, "msg": msg, "fp": fp or hashlib.md5((cat + msg).encode()).hexdigest()[:10]})

    for m in col.get("models", []):
        if not m.get("ok"):
            add("P0", "模型", "%s(%s) 不可用 rc=%s" % (m["model"], m["role"], m.get("rc")))

    bal = (col.get("keys") or {}).get("deepseek_balance")
    if bal is not None and bal < 20:
        add("P1", "余额", "DeepSeek 余额 ¥%.2f 偏低" % bal)

    root = next((r for r in col.get("disk", []) if r["mount"] == "/"), None)
    if root:
        if root["pct"] >= 92:
            add("P0", "磁盘", "根盘使用率 %d%%" % root["pct"])
        elif root["pct"] >= 85:
            add("P1", "磁盘", "根盘使用率 %d%%" % root["pct"])
    fc = forecast()
    if fc and fc.get("days_left") is not None and fc["days_left"] < 14:
        add("P1", "磁盘", "按当前增速 %.2f%%/天，约 %d 天到 90%%" % (fc["rate"], fc["days_left"]))

    gaps = (col.get("rpo") or {}).get("gaps") or []
    if gaps:
        add("P0", "备份", "RPO 缺口: " + ", ".join(gaps[:3]))

    for a in col.get("agents", []):
        if a.get("workspace_ok") is False:
            add("P1", "管家", "%s 工作区缺失" % a.get("id"))

    for line in tail_err(os.path.join(ST, "eh-health.log"), 26):
        if "WARN" in line or "异常" in line:
            add("P1", "EH", line[:120])

    for line in tail_err(os.path.join(ST, "cron-alert.log"), 26):
        add("P1", "定时任务", line[:120])

    for line in tail_err(os.path.join(ST, "store-snapshot.log"), 26):
        add("P1", "快照", line[:120])

    order = {"P0": 0, "P1": 1, "P2": 2}
    items.sort(key=lambda x: order[x["sev"]])

    md = ["# 体检日报 %s" % NOW.strftime("%Y-%m-%d %H:%M"), ""]
    md.append("## 采集概览")
    md.append("- 模型: " + ", ".join("%s=%s" % (m["model"].split("/")[-1], "OK" if m["ok"] else "FAIL") for m in col.get("models", [])))
    md.append("- 管家: %d 个" % len(col.get("agents", [])))
    md.append("- 余额: %s" % ("¥%.2f" % bal if bal is not None else "不可用"))
    md.append("- 磁盘: " + ", ".join("%s %d%%" % (r["mount"], r["pct"]) for r in col.get("disk", [])))
    md.append("- 备份日历(近14天缺): " + (", ".join(gaps) if gaps else "无缺口"))
    md.append("")
    md.append("## 发现")
    if items:
        for it in items:
            md.append("- [%s] %s: %s" % (it["sev"], it["cat"], it["msg"]))
    else:
        md.append("- 全部正常")
    open(os.path.join(AUD, "daily-report.md"), "w").write("\n".join(md) + "\n")

    statep = os.path.join(AUD, "report-state.json")
    st = load(statep, {}) or {}
    sent = st.get("sent", {})
    now = time.time()
    fresh = [i for i in items if now - sent.get(i["fp"], 0) > 21600]
    if fresh:
        head = "体检日报 %s：P0=%d P1=%d" % (NOW.strftime("%m-%d %H:%M"),
                                             len([i for i in items if i["sev"] == "P0"]),
                                             len([i for i in items if i["sev"] == "P1"]))
        body = "\n".join("- [%s] %s: %s" % (i["sev"], i["cat"], i["msg"]) for i in fresh[:8])
        try:
            subprocess.run(["bash", NOTIFY, head + "\n" + body], timeout=90)
        except Exception:
            pass
        for i in fresh:
            sent[i["fp"]] = now
        st["sent"] = {k: v for k, v in sent.items() if now - v < 172800}
        json.dump(st, open(statep, "w"))
    print(json.dumps({"items": len(items), "sent": len(fresh), "report": os.path.join(AUD, "daily-report.md")}, ensure_ascii=False))

if __name__ == "__main__":
    main()
