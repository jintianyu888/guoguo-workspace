#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会话异常哨兵 v1.1（只读）

2026-11-01 主公令「脚本盯着」；双审 2026-11-01 18:14 qianwen-token-plan/qwen3.8-max
+ zai/glm-5.3（两路均「有条件通过」，Must 已逐条落地；评审记录见
state/work/cross-review/20261101-180832/ 与 /tmp/zhipu-rev2.txt）。

只读扫网关日志，发现会话级异常族按阈值告警。不重启、不改库、不删文件。
判定写 JSON，退出码恒 0（避免 cron 报错风暴）。

用法: session-guard.py [--from-file F] [--window MIN] [--json] [--no-alert]
"""
import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

WS = os.environ.get("OPENCLAW_WS", "/home/j/.openclaw/workspace")
STATE = os.path.join(WS, "state", "session-guard")
EVENTS = os.path.join(STATE, "events.jsonl")
LAST_ALERT = os.path.join(STATE, "last-alert.json")
LAST_RUN = os.path.join(STATE, "last-run.json")
SCAN_FAIL_FLAG = os.path.join(STATE, "scan-failed.json")
LOCK = os.path.join(STATE, ".lock")
STAB = os.path.join(WS, "state", "stability", "latest.md")
NOTIFY = os.path.join(WS, "tools", "notify.sh")
LOG = "/usr/bin/journalctl"

# (阈值, 正则, 中文说明)
PATTERNS = {
    "P1_legacy_transcript": (10, re.compile(r"Persisted legacy session transcripts require doctor"), "legacy transcript 守卫"),
    "P2_dispatch_refresh": (3, re.compile(r"DispatchSessionRefreshRequiredError"), "飞书入站派发会话票失效"),
    "P3_session_event": (3, re.compile(r"Session event was not admitted"), "会话事件未准入"),
}
UNKNOWN_THRESHOLD = 10
DEDUPE_SECONDS = 6 * 3600
MAX_ALERT_ENTRIES = 500
DISK_MIN_BYTES = 200 * 1024 * 1024
ROTATE_SECONDS = 30 * 86400
STAB_MAX_AGE = 45 * 60

KEY_RE = re.compile(r'agent:[a-z0-9][a-z0-9_-]*:[^\s"\',]+')
FALLBACK_RE = re.compile(r"conn=([0-9a-f]{6,})", re.I)
KEY_TRAIL = '.,;:)]}>\'"'


def now_ts():
    return int(time.time())


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_log(window_min, from_file=None):
    """返回 (文本, error_kind, error_detail)。error_kind 为 None 表示成功。"""
    if from_file:
        try:
            with open(from_file, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read(), None, None
        except OSError as exc:
            return "", "read-failed", str(exc)
    try:
        proc = subprocess.run(
            [LOG, "--user", "-u", "openclaw-gateway", "--since", "-%d min" % window_min, "--no-pager"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "", "journalctl-failed", str(exc)
    if proc.returncode != 0:
        return "", "journalctl-rc", "rc=%d %s" % (proc.returncode, (proc.stderr or "").strip()[:200])
    return proc.stdout or "", None, None


def gateway_active():
    try:
        proc = subprocess.run(["systemctl", "--user", "is-active", "openclaw-gateway"],
                              capture_output=True, text=True, timeout=10)
        state = (proc.stdout or "").strip()
        if state in ("inactive", "failed", "deactivating"):
            return False
        return True  # active 或无法判定：按活着处理，宁可告警不漏告警
    except (OSError, subprocess.SubprocessError):
        return True  # 判不了就当活着，宁可告警


def stability_says_down():
    """仅当 stability 结果新鲜且明确判死时才静默。"""
    try:
        age = now_ts() - int(os.path.getmtime(STAB))
    except OSError:
        return False
    if age > STAB_MAX_AGE:
        return False
    try:
        with open(STAB, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(4000)
    except OSError:
        return False
    if "GatewayDown" in head:
        return True
    for line in head.splitlines()[:40]:
        if "网关" in line and ("FAIL" in line or "DOWN" in line):
            return True
    return False


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False


def append_events(records):
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(EVENTS, "a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def rotate_events():
    try:
        if now_ts() - int(os.path.getmtime(EVENTS)) < ROTATE_SECONDS:
            return
    except OSError:
        return
    try:
        with open(LOCK, "w") as lf:
            try:
                fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return
            cutoff = now_ts() - ROTATE_SECONDS
            keep = []
            with open(EVENTS, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if int(rec.get("ts", 0)) >= cutoff:
                        keep.append(line)
            tmp = EVENTS + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.writelines(keep)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, EVENTS)
    except OSError:
        pass


def extract_key(line):
    m = KEY_RE.search(line)
    if m:
        return m.group(0).rstrip(KEY_TRAIL)[:200]
    m = FALLBACK_RE.search(line)
    if m:
        return "conn=" + m.group(1)
    return "unknown"


def prune_last_alert(last, ts):
    fresh = {}
    for k, v in last.items():
        try:
            if ts - int(v) < DEDUPE_SECONDS:
                fresh[k] = int(v)
        except (TypeError, ValueError):
            continue
    if len(fresh) > MAX_ALERT_ENTRIES:
        ordered = sorted(fresh.items(), key=lambda kv: kv[1], reverse=True)[:MAX_ALERT_ENTRIES]
        fresh = dict(ordered)
    return fresh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-file")
    ap.add_argument("--window", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-alert", action="store_true")
    args = ap.parse_args()

    started = now_ts()
    buckets = {}
    log_text, err_kind, err_detail = read_log(args.window, args.from_file)
    scanned = len(log_text.splitlines()) if log_text else 0

    if err_kind:
        status = "scan-failed"
    elif scanned == 0:
        status = "no-log"
    else:
        status = "ok"

    if log_text:
        for line in log_text.splitlines():
            for name, (thr, rx, _desc) in PATTERNS.items():
                if not rx.search(line):
                    continue
                key = extract_key(line)
                b = buckets.setdefault((name, key), {"count": 0, "sample": ""})
                b["count"] += 1
                if not b["sample"]:
                    b["sample"] = line.strip()[:200]

    fired = []
    for (name, key), b in buckets.items():
        thr = PATTERNS[name][0]
        if key == "unknown":
            thr = max(thr, UNKNOWN_THRESHOLD)
        if b["count"] >= thr:
            fired.append({"pattern": name, "sessionKey": key, "count": b["count"],
                          "threshold": thr, "sample": b["sample"]})

    gwy_up = gateway_active()
    silenced = False
    if fired and (not gwy_up or stability_says_down()):
        silenced = True
        status = "silenced-by-stability"

    ts = now_ts()
    last = prune_last_alert(load_json(LAST_ALERT, {}), ts)
    to_alert = []
    for item in fired:
        k = item["pattern"] + "|" + item["sessionKey"]
        if ts - int(last.get(k, 0) or 0) >= DEDUPE_SECONDS:
            to_alert.append(item)

    try:
        disk_low = shutil.disk_usage("/home").free < DISK_MIN_BYTES
    except OSError:
        disk_low = False

    records = []
    for item in fired:
        records.append({
            "ts": ts, "pattern": item["pattern"], "sessionKey": item["sessionKey"],
            "count": item["count"], "threshold": item["threshold"],
            "alertable": any(item is x for x in to_alert), "silenced": silenced,
            "sample": item["sample"],
        })

    wrote = False
    if disk_low:
        status = "disk-low"
    elif records:
        wrote = append_events(records)
        rotate_events()

    alerted = 0
    notify_error = None
    if to_alert and not silenced and not args.no_alert:
        lines = ["🔁 会话异常哨兵"]
        for item in to_alert[:10]:
            lines.append("%s ×%d [%s] %s" % (PATTERNS[item["pattern"]][2], item["count"],
                                             item["pattern"], item["sessionKey"]))
        if len(to_alert) > 10:
            lines.append("…另有 %d 条（详见 state/session-guard/events.jsonl）" % (len(to_alert) - 10))
        lines.append("窗口 %d 分钟。处置：P1 → 建议 /new 或 openclaw doctor --session-sqlite inspect；"
                     "P2/P3 → 先观察，持续则提请重启窗口。" % args.window)
        try:
            subprocess.run(["bash", NOTIFY, "--alert", "\n".join(lines)],
                           capture_output=True, text=True, timeout=30)
            alerted = len(to_alert)
        except (OSError, subprocess.SubprocessError) as exc:
            alerted = 0
            notify_error = str(exc)
            status = "alert-failed"
        for item in to_alert:
            last[item["pattern"] + "|" + item["sessionKey"]] = ts
        save_json(LAST_ALERT, last)

    # 扫描失败：持续失败只告警一次，恢复即清标记
    scan_failed_alerted = False
    if err_kind:
        flag = load_json(SCAN_FAIL_FLAG, {})
        if not flag.get("alerted") and not args.no_alert:
            try:
                subprocess.run(["bash", NOTIFY, "--alert",
                                "⚠️ 会话异常哨兵扫描失败（%s）：%s\n处置：检查 journalctl 权限与磁盘。" %
                                (err_kind, (err_detail or "")[:200])],
                               capture_output=True, text=True, timeout=30)
                scan_failed_alerted = True
            except (OSError, subprocess.SubprocessError):
                pass
        save_json(SCAN_FAIL_FLAG, {"alerted": True, "since": flag.get("since", ts),
                                   "last_error": err_kind, "last_ts": ts})
    elif err_kind is None and os.path.exists(SCAN_FAIL_FLAG):
        try:
            os.unlink(SCAN_FAIL_FLAG)
        except OSError:
            pass

    result = {
        "ts": ts, "time": iso(ts), "status": status, "window_min": args.window,
        "scanned_lines": scanned, "buckets": len(buckets), "fired": len(fired),
        "alerted": alerted, "silenced": silenced, "disk_low": disk_low,
        "events_written": wrote, "gateway_active": gwy_up,
        "scan_failed_alerted": scan_failed_alerted,
        "error_kind": err_kind, "notify_error": notify_error,
        "error": (err_kind + ": " + (err_detail or "")) if err_kind else None,
        "duration_ms": int((time.time() - started) * 1000),
    }
    save_json(LAST_RUN, result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print("session-guard: status=%s scanned=%d fired=%d alerted=%d silenced=%s" % (
            result["status"], scanned, len(fired), alerted, silenced))
    return 0


if __name__ == "__main__":
    sys.exit(main())
