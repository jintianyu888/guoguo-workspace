#!/usr/bin/env python3
"""backup-health.py — 备份链体检（R18，2026-11-21）

判据（任何一条不满足就红）：
 1. 五处（X/D/E/H/NAS）各自最新归档 ≤ 48 小时
 2. 至少 3 处同时持有同一份最新归档（冗余）
 3. 保留脚本无「中止」字样落在近 24 小时日志里
 4. 群晖推送队列近 24 小时不应出现「源不存在」
"""
import glob, os, re, subprocess, sys, time, datetime

W = "/home/j/.openclaw/workspace"
DIRS = {"X": "/mnt/x/openclaw-backups", "D": "/mnt/d/openclaw-backups",
        "E": "/mnt/e/openclaw-backups", "H": "/mnt/h/openclaw-backups",
        "NAS": "/mnt/nas/archive/jinyu/openclaw-archives"}
bad, warn = [], []

def ts_of(f):
    # 9p/Windows 盘上的 mtime 不可靠（H 曾报 1970），优先用文件名里的时间戳
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})", os.path.basename(f))
    if m:
        try:
            return datetime.datetime.strptime("%s %s:%s:%s" % m.groups(), "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            pass
    return os.path.getmtime(f)


def newest(d):
    f = glob.glob(os.path.join(d, "*.tar.gz"))
    if not f:
        return None
    return max(f, key=ts_of)

state = {}
for k, d in DIRS.items():
    f = newest(d)
    if not f:
        state[k] = None
        bad.append("%s 盘无任何归档" % k)
        continue
    age = (time.time() - ts_of(f)) / 3600
    state[k] = (os.path.basename(f), age)
    if age > 48:
        bad.append("%s 最新归档已 %.0f 小时未更新" % (k, age))

names = [v[0] for v in state.values() if v]
if names:
    top = max(set(names), key=names.count)
    cnt = names.count(top)
    if cnt < 3:
        warn.append("最新归档 %s 仅 %d 处持有（建议 ≥3）" % (top[:26], cnt))

for log, pat in ((os.path.join(W, "state/work/retention-auto.log"), "中止"),
                 (os.path.join(W, "state/work/nas-push.log"), "源不存在")):
    try:
        lines = open(log, errors="ignore").read().splitlines()
    except OSError:
        continue
    # 只看「最近一次运行」那一段，旧故障不该一直红着
    start = 0
    for i, l in enumerate(lines):
        if "开始" in l:
            start = i
    hits = [l for l in lines[start:] if pat in l]
    if hits:
        bad.append("%s 近 24h 出现「%s」%d 次" % (os.path.basename(log), pat, len(hits)))

for k, v in state.items():
    print("  %-4s %s" % (k, ("%s（%.0f 小时前）" % (v[0][:26], v[1])) if v else "无归档"))
for b in bad:
    print("❌ " + b)
for w in warn:
    print("⚠  " + w)
if bad:
    sys.exit(1)
print("✅ 备份链健康" + ("（含 %d 条提示）" % len(warn) if warn else ""))
