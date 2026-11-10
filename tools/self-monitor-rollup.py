#!/usr/bin/env python3
"""按天聚合 self-monitor 历史 → state/self-monitor/daily.csv（保留 90 天）
用法: self-monitor-rollup.py            # 汇总昨天
      self-monitor-rollup.py --all      # 汇总全部可得日期
      self-monitor-rollup.py --date 2026-10-23
"""
import re, sys, os, json, datetime, statistics, collections

ST = "/home/j/.openclaw/workspace/state/self-monitor"
HIST = os.path.join(ST, "history.log")
CSV = os.path.join(ST, "daily.csv")
KEEP = 90

pat = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}):\d{2}:\d{2}.*?mem=(\d+)%.*?swap=(\d+)%.*?load=([\d.]+)")

def collect():
    d = collections.defaultdict(list)
    for line in open(HIST, encoding="utf-8", errors="ignore"):
        m = pat.match(line)
        if m:
            d[m.group(1)].append((int(m.group(3)), int(m.group(4)), float(m.group(5))))
    return d

def rows(d, only=None):
    out = {}
    for day, v in d.items():
        if only and day != only:
            continue
        loads = sorted(x[2] for x in v)
        p95 = loads[max(0, int(len(loads) * 0.95) - 1)]
        out[day] = {
            "date": day, "samples": len(v),
            "load_mean": round(statistics.mean(loads), 2),
            "load_p95": round(p95, 2),
            "load_max": round(max(loads), 2),
            "mem_mean": round(statistics.mean(x[0] for x in v), 1),
            "mem_max": max(x[0] for x in v),
            "swap_mean": round(statistics.mean(x[1] for x in v), 1),
        }
    return out

def write(out):
    existing = {}
    if os.path.exists(CSV):
        for line in open(CSV, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                r = json.loads(line)
                existing[r["date"]] = r
            except Exception:
                pass
    existing.update(out)
    keys = sorted(existing)[-KEEP:]
    tmp = CSV + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# 按天聚合，保留最近 %d 天；字段: date,samples,load_mean,load_p95,load_max,mem_mean,mem_max,swap_mean\n" % KEEP)
        for k in keys:
            f.write(json.dumps(existing[k], ensure_ascii=False) + "\n")
    os.replace(tmp, CSV)
    return len(keys)

if __name__ == "__main__":
    args = sys.argv[1:]
    d = collect()
    if "--all" in args:
        out = rows(d)
    elif "--date" in args:
        out = rows(d, args[args.index("--date") + 1])
    else:
        y = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        out = rows(d, y)
    n = write(out)
    print("rollup %d day(s) → %s (共 %d 天)" % (len(out), CSV, n))
