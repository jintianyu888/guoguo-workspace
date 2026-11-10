#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stability-metrics.py v1 —— 稳定性指标报表（错误率/问题率/稳定率/重启率/崩溃率 + 趋势）
用法: stability-metrics.py [--days 7] [--quiet]
输出: state/reports/stability-metrics-<YYYYMMDD>.md  + 单行摘要到 stdout
只用 stdlib；journal 一次性流式读取，避免多次扫描。
"""
import argparse, csv, json, os, re, subprocess, sys, datetime as dt
from collections import Counter, defaultdict

WS = "/home/j/.openclaw/workspace"
OUTD = os.path.join(WS, "state/reports")
UNIT = "openclaw-gateway"
OFFLINE_WINDOWS = [(4, 6)]  # 04:00-06:05 计划内离线窗（路由器重启+备份）

def run(cmd, timeout=300):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return 1, "", str(e)

def in_offline(hour):
    return any(hour >= a and hour < b + 1 for a, b in OFFLINE_WINDOWS)

def norm_sig(line):
    s = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*", "", line)
    s = re.sub(r"\b\d{2,}\b", "N", s)
    s = re.sub(r"0x[0-9a-f]+", "HEX", s)
    s = re.sub(r"[a-f0-9]{8}-[a-f0-9-]{20,}", "UUID", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:160]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    days = max(1, a.days)
    now = dt.datetime.now()
    since = now - dt.timedelta(days=days)

    # ---- journal 一次性读取 ----
    rc, out, err = run('journalctl --user -u %s --since "%s" -o short-iso --no-pager' % (UNIT, since.strftime("%Y-%m-%d %H:%M:%S")), timeout=600)
    if rc != 0 and not out:
        print("journalctl 读取失败: %s" % (err or rc)); return 2

    err_by_day = Counter(); err_by_day_planned = Counter()
    sig = Counter(); restarts_by_day = Counter(); crash_by_day = Counter()
    err_by_hour = Counter(); total_lines = 0; restart_events = []
    pat_restart = re.compile(r"openclaw-gateway\.service: (Started|Stopped|Starting|Stopping|Deactivated|Scheduled restart)", re.I)
    pat_crash = re.compile(r"(openclaw-gateway.*(SIGKILL|SIGSEGV|core dumped|out of memory|oom-kill))|(Main process exited, code=(killed|dumped|signal))|(Failed with result '(signal|core-dump|oom-kill)')", re.I)
    pat_err = re.compile(r"\b(error|exception|failed|failure|timeout|refused|ECONN|EPIPE)\b", re.I)
    for line in out.splitlines():
        total_lines += 1
        m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):", line)
        if not m:
            continue
        day, hour = m.group(1), int(m.group(2))
        if pat_err.search(line):
            err_by_day[day] += 1
            err_by_hour["%s-%02d" % (day, hour)] += 1
            if in_offline(hour):
                err_by_day_planned[day] += 1
            else:
                sig[norm_sig(line)] += 1
        mr = pat_restart.search(line)
        if mr:
            restarts_by_day[day] += 1
            try:
                ts = dt.datetime.strptime("%s %s" % (day, line.split("T")[1][:8]), "%Y-%m-%d %H:%M:%S")
            except Exception:
                ts = None
            if ts: restart_events.append((ts, mr.group(1).lower()))
        if pat_crash.search(line):
            crash_by_day[day] += 1

    # ---- 可用率：最近一次 ActiveEnter 至今 ----
    rc2, s2, _ = run('systemctl --user show %s -p ActiveEnterTimestamp -p NRestarts -p ActiveState' % UNIT)
    active_since, nrestarts, state = None, 0, "unknown"
    for ln in s2.splitlines():
        if "=" not in ln: continue
        k, v = ln.split("=", 1)
        if k == "ActiveEnterTimestamp":
            try:
                raw = re.sub(r"\s+[A-Z]{2,5}$", "", v.split(" (")[0].strip())
                active_since = dt.datetime.strptime(raw, "%a %Y-%m-%d %H:%M:%S")
            except Exception: pass
        elif k == "NRestarts":
            try: nrestarts = int(v)
            except Exception: pass
        elif k == "ActiveState":
            state = v
    period_s = (now - since).total_seconds()
    # 可用率 = 1 - 真实停机间隙/窗口（停机=Stopped→下一个Started之间）
    downtime = 0.0; down_at = None; starts = 0
    for ts, kind in sorted(restart_events):
        if kind.startswith(("stopped", "stopping", "deactivated")):
            if down_at is None: down_at = ts
        elif kind.startswith(("started", "starting")):
            starts += 1
            if down_at is not None:
                downtime += max(0.0, (ts - down_at).total_seconds()); down_at = None
    if down_at is not None:
        downtime += max(0.0, (now - down_at).total_seconds())
    downtime = max(0.0, min(downtime, period_s))
    avail = (1.0 - downtime / period_s) * 100.0 if period_s > 0 else None

    # ---- 稳定性检查历史（WARN/FAIL 计数） ----
    stab = {"runs": 0, "warn": 0, "fail": 0}
    try:
        with open(os.path.join(WS, "state/stability/latest.json")) as f:
            j = json.load(f)
        for it in (j.get("items") or []):
            st = (it.get("status") or "").upper()
            stab["runs"] += 1
            if st == "WARN": stab["warn"] += 1
            elif st == "FAIL": stab["fail"] += 1
    except Exception:
        pass

    # ---- 主机负载（self-monitor） ----
    load = {}
    try:
        with open(os.path.join(WS, "state/self-monitor/daily.csv")) as f:
            rows = [r for r in csv.DictReader((l for l in f if not l.startswith("#")))]
        for r in rows[-days:]:
            load[r["date"]] = r
    except Exception:
        pass

    days_list = [(since + dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days + 1)]
    half = max(1, len(days_list) // 2)
    recent, prior = days_list[-half:], days_list[:-half]

    def agg(cnt, keys):
        vals = [cnt.get(k, 0) for k in keys]
        return sum(vals), (sum(vals) / len(vals) if vals else 0.0)

    r_err, r_err_avg = agg(err_by_day, recent)
    p_err, p_err_avg = agg(err_by_day, prior)
    r_rs, _ = agg(restarts_by_day, recent)
    p_rs, _ = agg(restarts_by_day, prior)
    r_cr, _ = agg(crash_by_day, recent)
    p_cr, _ = agg(crash_by_day, prior)
    planned_total = sum(err_by_day_planned.values())
    unplanned_total = sum(err_by_day.values()) - planned_total

    def trend(new, old):
        if old == 0:
            return "新增" if new > 0 else "持平"
        d = (new - old) / old * 100.0
        return ("↓%.0f%%" % -d) if d < 0 else ("↑%.0f%%" % d if d > 0 else "持平")

    total_err = sum(err_by_day.values()) or 1
    md = []
    md.append("# 稳定性指标报表 v1")
    md.append("")
    md.append("- 生成时间：%s" % now.strftime("%Y-%m-%d %H:%M:%S"))
    md.append("- 统计窗口：近 %d 天（%s → %s）" % (days, since.strftime("%m-%d"), now.strftime("%m-%d")))
    md.append("- 数据源：journalctl(%s) / systemctl / state/stability / state/self-monitor" % UNIT)
    md.append("")
    md.append("## 1. 五项核心指标")
    md.append("")
    md.append("| 指标 | 近半窗 | 前半窗 | 趋势 | 口径 |")
    md.append("|---|---|---|---|---|")
    md.append("| 错误率 | %d 条/日 | %d 条/日 | %s | journal 含 error/failed/timeout 计 |" % (r_err_avg, p_err_avg, trend(r_err_avg, p_err_avg)))
    md.append("| 问题率 | WARN %d / FAIL %d | — | — | 最近一次稳定性自检 17 项 |" % (stab["warn"], stab["fail"]))
    md.append("| 稳定率 | %s | — | — | 1 - 真实停机间隙/窗口（停机 %s） |" % (("%.3f%%" % avail) if avail is not None else "未采集", ("%d 秒" % int(downtime)) if avail is not None else "—"))
    md.append("| 重启率 | %d 次 | %d 次 | %s | journal 中 Started/Stopped 事件 |" % (r_rs, p_rs, trend(r_rs, p_rs)))
    md.append("| 异常退出 | %d 次 | %d 次 | %s | 含子进程 SIGKILL/OOM/非零退出（非网关本体） |" % (r_cr, p_cr, trend(r_cr, p_cr)))
    md.append("")
    md.append("## 2. 错误构成")
    md.append("")
    md.append("- 计划内（04:00-06:05 离线窗，路由器重启+备份）：%d 条（占 %.1f%%）" % (planned_total, planned_total / total_err * 100))
    md.append("- 计划外：%d 条（占 %.1f%%）——**这才是该压降的部分**" % (unplanned_total, unplanned_total / total_err * 100))
    if sig:
        md.append("")
        md.append("计划外 Top 8 错误签名：")
        md.append("")
        for s, c in sig.most_common(8):
            md.append("- ×%d %s" % (c, s))
    md.append("")
    md.append("## 3. 进程与主机")
    md.append("")
    md.append("- 网关状态：%s｜NRestarts=%d｜本次在线自 %s｜窗口内启动 %d 次" % (state, nrestarts, active_since.strftime("%Y-%m-%d %H:%M") if active_since else "未知", starts))
    if load:
        ks = sorted(load)[-3:]
        for k in ks:
            r = load[k]
            md.append("- %s：负载均值 %s / 峰值 %s｜内存均值 %s%% / 峰值 %s%%" % (k, r.get("load_mean"), r.get("load_max"), r.get("mem_mean"), r.get("mem_max")))
    md.append("")
    md.append("## 4. 结论")
    md.append("")
    worse = []
    if p_err_avg and r_err_avg > p_err_avg * 1.1: worse.append("错误率上升")
    if p_rs and r_rs > p_rs: worse.append("重启次数增加")
    if p_cr and r_cr > p_cr: worse.append("崩溃次数增加")
    md.append("- 趋势判定：%s" % ("、".join(worse) if worse else "整体持平或改善"))
    md.append("- 压降重点：计划外错误占 %.1f%%，优先处理上面 Top 签名中出现频率最高的三类" % (unplanned_total / total_err * 100))
    md.append("")

    os.makedirs(OUTD, exist_ok=True)
    path = os.path.join(OUTD, "stability-metrics-%s.md" % now.strftime("%Y%m%d"))
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(md) + "\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

    summary = "稳定性：错误 %d→%d 条/日(%s)｜重启 %d→%d｜崩溃 %d→%d｜稳定率 %s｜计划外错误 %d 条" % (
        int(p_err_avg), int(r_err_avg), trend(r_err_avg, p_err_avg), p_rs, r_rs, p_cr, r_cr,
        ("%.2f%%" % avail) if avail is not None else "未采集", unplanned_total)
    if not a.quiet:
        print(summary)
        print("报告：%s" % path)
    return 0

if __name__ == "__main__":
    sys.exit(main())
