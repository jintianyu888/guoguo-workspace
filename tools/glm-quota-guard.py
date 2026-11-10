#!/usr/bin/env python3
"""glm-quota-guard.py v0.3 — GLM 配额守卫（双源）
① 面板积分 quotas.json：周额度≥85% 或 5小时窗口打满 → 降级
② 日志限流：6h 内 zai/glm 出现 429/1305/rate limit ≥3 次 → 降级 5 小时
输出 state/model-econ/glm-quota-state.json，状态翻转时飞书通知。
只读判断，不改任何模型配置。
"""
import json, os, subprocess, sys, time
from datetime import datetime, timedelta

WS = "/home/j/.openclaw/workspace"
STATE = WS + "/state/model-econ/glm-quota-state.json"
PANEL = WS + "/state/model-econ/quotas.json"
WEEKLY_HIGH = 85
LOG_HITS_TRIP = 3
LOG_WINDOW_H = 6

def load_json(p, d=None):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return d if d is not None else {}

def parse_ts(s):
    if not s: return None
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(s.strip(), f)
        except Exception: pass
    return None

def log_hits():
    try:
        p = subprocess.run(["journalctl", "--user", "-u", "openclaw-gateway",
                            "--since", "-%dh" % LOG_WINDOW_H, "--no-pager"],
                           capture_output=True, text=True, timeout=60)
        n = 0
        for ln in p.stdout.splitlines():
            low = ln.lower()
            if "zai" in low or "glm" in low:
                if any(k in low for k in ("429", "1305", "rate limit", "rate_limit", "quota")):
                    n += 1
        return n
    except Exception:
        return 0

def notify(msg):
    try:
        subprocess.run(["bash", WS + "/tools/notify.sh", msg], capture_output=True, timeout=90)
    except Exception:
        pass

def main():
    now = datetime.now()
    tripped, until, reasons = False, None, []
    hits = log_hits()
    if hits >= LOG_HITS_TRIP:
        tripped = True
        until = now + timedelta(hours=5)
        reasons.append("日志限流 %d 次/6h" % hits)

    z = (load_json(PANEL, {}).get("providers") or {}).get("zai") or {}
    wk, win = z.get("weekly_pct"), z.get("window_pct")
    if isinstance(wk, (int, float)) and wk >= WEEKLY_HIGH:
        tripped = True
        r = parse_ts(z.get("weekly_reset_at")) or (now + timedelta(days=2))
        if until is None or r > until: until = r
        reasons.append("周额度 %d%%（余 %s 积分）" % (wk, z.get("weekly_credits_limit", 0) - z.get("weekly_credits_used", 0)))
    if isinstance(win, (int, float)) and win >= 100:
        tripped = True
        r = parse_ts(z.get("window_reset_at")) or (now + timedelta(hours=5))
        if r <= now: r = now + timedelta(hours=5)
        if until is None or r > until: until = r
        reasons.append("5小时窗口已打满")

    prev = bool(load_json(STATE, {}).get("tripped", False))
    st = {
        "tripped": tripped,
        "until": int(until.timestamp()) if until else 0,
        "until_iso": until.strftime("%Y-%m-%d %H:%M") if until else "",
        "reason": "；".join(reasons),
        "hits_6h": hits,
        "panel_weekly_pct": wk, "panel_window_pct": win,
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f: json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)

    if prev != tripped:
        if tripped:
            notify("🔴 GLM 降级：%s。规划层暂时绕开 GLM，恢复约 %s" % (st["reason"], st["until_iso"]))
        else:
            notify("🟢 GLM 恢复：面板积分回到安全线，恢复调度")
    print(json.dumps(st, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
