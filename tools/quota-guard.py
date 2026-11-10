#!/usr/bin/env python3
"""quota-guard.py —— 四家配额守卫（合并 GLM配额守卫 + balance-alert 的判断逻辑）

2026-10-24 落地 A 方案，补齐两家评审的必改项：
B1 频率模型冲突 → 本脚本**只读** quotas.json / balances.json，绝不抓页面，
   与 quota-scrape.py 的 25–45 分钟随机间隔无冲突；数据过期只报“陈旧”，不判额度。
B2 限流日志来源 → 不臆造 429 数据源；只认 quotas.json 里真实存在的字段
   （zai 窗口/周额度、kimi 月用量、minimax 5h/周），缺失就标记 no-data。
另补：阈值进 guard-config.json（不再硬编码）、去重 key = 厂商+级别、告警有次数上限、
降级标记写进 balances.json 供面板消费（不是写完没人看）、默认 --dry-run。
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ECON = os.path.join(BASE, "state", "model-econ")
QUOTAS = os.path.join(ECON, "quotas.json")
BALANCES = os.path.join(ECON, "balances.json")
CONFIG = os.path.join(ECON, "guard-config.json")
DEDUPE = os.path.join(ECON, "guard-dedupe.json")
DECISIONS = os.path.join(ECON, "guard-decisions.jsonl")
NOTIFY = os.path.join(BASE, "tools", "notify.sh")

DEFAULTS = {
    "fresh_minutes": 90,          # 数据超过这么久算陈旧
    "dedupe_hours": 6,            # 同厂商同级别告警冷却
    "deepseek_balance_cny": 30,   # DeepSeek 余额低于此值告警
    "weekly_pct": 85,             # 周额度使用率告警线
    "window_pct": 100,            # 5 小时窗口打满线
    "month_pct": 90,              # 月额度使用率告警线
    "max_alerts_per_run": 3,      # 单次最多告警条数（防止刷屏）
}


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def age_minutes(stamp):
    try:
        dt = datetime.strptime(stamp, "%Y-%m-%d %H:%M")
    except Exception:
        return None
    return (datetime.now() - dt).total_seconds() / 60.0


def main():
    dry = "--dry-run" in sys.argv
    cfg = dict(DEFAULTS)
    cfg.update(load(CONFIG, {}) or {})
    quotas = load(QUOTAS, {}) or {}
    balances = load(BALANCES, {}) or {}
    dedupe = load(DEDUPE, {}) or {}
    now = time.time()
    alerts = []          # (key, level, text)
    degraded = {}        # vendor -> reason

    provs = quotas.get("providers", {}) or {}
    for vendor, st in provs.items():
        if not isinstance(st, dict):
            continue
        if st.get("status") not in ("ok", "locked", None):
            alerts.append((vendor + ":stale", "warn",
                           "%s 抓取状态异常（%s），本轮不判额度" % (vendor, st.get("status"))))
            continue
        age = age_minutes(st.get("captured_at") or "")
        if age is None or age > cfg["fresh_minutes"]:
            alerts.append((vendor + ":stale", "warn",
                           "%s 配额数据已 %s 分钟未更新，本轮不判额度" %
                           (vendor, int(age) if age is not None else "?")))
            continue
        label = st.get("label") or vendor
        wp = st.get("weekly_pct")
        win = st.get("window_pct")
        mp = st.get("month_used_pct") or st.get("month_pct")
        if isinstance(wp, (int, float)) and wp >= cfg["weekly_pct"]:
            alerts.append((vendor + ":weekly", "crit",
                           "%s 周额度已用 %s%%（阈值 %s%%）" % (label, wp, cfg["weekly_pct"])))
            degraded[vendor] = "weekly>=%s%%" % cfg["weekly_pct"]
        if isinstance(win, (int, float)) and win >= cfg["window_pct"]:
            alerts.append((vendor + ":window", "crit",
                           "%s 5 小时窗口已打满（%s%%）" % (label, win)))
            degraded.setdefault(vendor, "window>=%s%%" % cfg["window_pct"])
        if isinstance(mp, (int, float)) and mp >= cfg["month_pct"]:
            alerts.append((vendor + ":month", "crit",
                           "%s 月额度已用 %s%%（阈值 %s%%）" % (label, mp, cfg["month_pct"])))
            degraded.setdefault(vendor, "month>=%s%%" % cfg["month_pct"])

    ds = (balances.get("providers", {}) or {}).get("deepseek", {}) or {}
    bal = ds.get("available")
    if isinstance(bal, (int, float)) and bal < cfg["deepseek_balance_cny"]:
        alerts.append(("deepseek:balance", "warn",
                       "DeepSeek 余额 ¥%.2f，低于阈值 ¥%s" % (bal, cfg["deepseek_balance_cny"])))

    # 去重（key = 厂商+级别），并在冷却窗口内抑制
    fresh = []
    for key, level, msg in alerts:
        last = dedupe.get(key)
        if last and now - last < cfg["dedupe_hours"] * 3600:
            continue
        dedupe[key] = now
        fresh.append((key, level, msg))
    capped = fresh[: cfg["max_alerts_per_run"]]

    # 降级标记写进 balances.json（面板逐行读，消费端存在）
    for vendor, reason in degraded.items():
        row = (balances.get("providers", {}) or {}).get(vendor)
        if isinstance(row, dict):
            row["degraded"] = True
            row["degraded_reason"] = reason
            row["degraded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    record = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "dry_run": dry, "alerts": [{"key": k, "level": l, "text": m} for k, l, m in capped],
              "degraded": degraded}
    with open(DECISIONS, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if dry:
        print(json.dumps(record, ensure_ascii=False, indent=1))
        return 0

    save(DEDUPE, dedupe)
    if degraded:
        save(BALANCES, balances)
    if capped:
        msg = "🚨【配额守卫】" + "；".join(m for _, _, m in capped)
        try:
            subprocess.run(["timeout", "30", "sh", NOTIFY, msg], timeout=45)
        except Exception as exc:
            print("notify failed: %s" % exc, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
