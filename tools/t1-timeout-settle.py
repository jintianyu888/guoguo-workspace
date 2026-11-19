#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""t1-timeout-settle.py — 用一次实测用时给定时任务定「墙钟超时」终值（2026-10-17 主公令）

背景：T1 重点备份原超时是估的 3600s。今晚 20:15 实跑一次，用真实用时 × 1.5 向上取整到
15 分钟，clamp 到 [1800, 10800]，写回 timeoutSeconds 并回读验证，再推飞书报账。

用法：
  python3 tools/t1-timeout-settle.py                 # 按默认 job 定值
  python3 tools/t1-timeout-settle.py --job <id>
  python3 tools/t1-timeout-settle.py --dry-run       # 只算不改
  python3 tools/t1-timeout-settle.py --job <id> --dry-run
退出码：0 正常（含「本次未成功，跳过」）；2 参数错误。
"""
import json
import os
import re
import subprocess
import sys
import time

W = os.path.expanduser("~/.openclaw/workspace")
LOG = os.path.join(W, "state/t1-settle.log")
NOTIFY = os.path.join(W, "tools/notify.sh")
TARGET = os.environ.get("NOTIFY_TARGET", "user:ou_74fec7bc81cc6ec6d2b4de1c0967923b")
DEFAULT_JOB = "f9bc976d-0aa6-49e9-92f3-454c3014b08d"  # T1重点备份(每日2次)
MIN_TO, MAX_TO, STEP = 1800, 10800, 900


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def sh(args, timeout=90):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except Exception as e:
        return 1, "", repr(e)


def json_tail(s):
    i = s.find("{")
    j = s.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(s[i:j + 1])
    except Exception:
        return None


def latest_run(job):
    rc, out, err = sh(["openclaw", "cron", "runs", job, "--json"])
    if rc != 0:
        log("cron runs rc=%s %s" % (rc, err[:150]))
        return None
    d = json_tail(out)
    if not d:
        log("cron runs 输出非 JSON")
        return None
    ents = [e for e in (d.get("entries") or []) if isinstance(e, dict)]
    fin = [e for e in ents if e.get("action") == "finished"]
    if not fin:
        return None
    return max(fin, key=lambda e: int(e.get("ts") or 0))


def duration_minutes(entry):
    s = str(entry.get("summary") or "")
    m = re.search(r"用时约\s*(\d+)\s*分钟", s)
    if m:
        return int(m.group(1))
    hits = [int(x) for x in re.findall(r"运行中\s*(\d+)\s*分钟", s)]
    return max(hits) if hits else None


def notify(text):
    try:
        p = subprocess.run(["bash", NOTIFY, text], capture_output=True, text=True, timeout=90)
        return p.returncode == 0
    except Exception:
        return False


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    job = DEFAULT_JOB
    if "--job" in argv:
        i = argv.index("--job")
        if i + 1 >= len(argv):
            print("--job 需要参数")
            return 2
        job = argv[i + 1]
    bad = [a for a in argv if a not in ("--dry-run", "--job", job)]
    if bad:
        print("未知参数: %s" % " ".join(bad))
        return 2

    rc, out, _ = sh(["openclaw", "cron", "get", job, "--json"])
    meta = json_tail(out) or {}
    name = (meta.get("job") or meta).get("name") or job[:8]

    entry = latest_run(job)
    if not entry:
        log("没有运行记录，跳过")
        print("无运行记录，跳过")
        return 0

    status = entry.get("status")
    ts = time.strftime("%m-%d %H:%M", time.localtime(int(entry.get("ts") or 0) / 1000))
    mins = duration_minutes(entry)

    if status != "ok" or not mins:
        msg = "⚠️ %s 定值跳过：最近一次运行 %s 状态=%s，用时解析=%s" % (name, ts, status, mins)
        log(msg)
        print(msg)
        if not dry:
            notify(msg)
        return 0

    need = int(-(-mins * 60 * 3 // 2 // STEP) * STEP)   # 1.5x，向上取整到 15min
    final = max(MIN_TO, min(MAX_TO, need))

    if dry:
        print("测得 %d 分钟 → 终值 %ds（dry-run，未写）" % (mins, final))
        return 0

    rc, out, err = sh(["openclaw", "cron", "edit", job, "--timeout-seconds", str(final)])
    if rc != 0:
        msg = "❌ %s 定值写入失败 rc=%s %s" % (name, rc, err[:120])
        log(msg)
        notify(msg)
        return 0

    rc2, out2, _ = sh(["openclaw", "cron", "get", job, "--json"])
    got = None
    d = json_tail(out2) or {}
    jj = d.get("job") or d
    got = ((jj.get("payload") or {}).get("timeoutSeconds"))

    ok = (got == final)
    msg = ("%s %s：实测 %d 分钟 → 超时终值 %ds（1.5x，上下限 %d–%d）｜回读=%s"
           % ("✅" if ok else "⚠️", name, mins, final, MIN_TO, MAX_TO, got))
    log(msg)
    notify(msg)
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
