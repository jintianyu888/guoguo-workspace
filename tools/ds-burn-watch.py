#!/usr/bin/env python3
"""ds-burn-watch.py — 余额烧钱对账（只读，带互斥锁 + 原子追加）
每次运行：读 DeepSeek 余额 + 统计本机最近 INTERVAL 内的模型 token，写 CSV 并算有效单价。
并发加固（2026-10-17 双评审要求）：
  - 全局 flock 互斥，重叠运行直接退出（绝不并发写同一 CSV）
  - sqlite 只读 + busy_timeout，避免 database is locked
  - 整行 O_APPEND 单次写入，不产生半行
输出：state/ds-burn.csv
"""
import os, json, sqlite3, subprocess, time, fcntl, sys

WS = "/home/j/.openclaw/workspace"
DB = os.path.expanduser("~/.openclaw/agents/main/agent/openclaw-agent.sqlite")
LOG = os.path.join(WS, "state", "ds-burn.csv")
LOCK = os.path.join(WS, "state", "ds-burn.lock")
INTERVAL = 600

def main():
    lf = open(LOCK, "a+")
    try:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("skip: another run in progress")
        return 0

    def balance():
        try:
            out = subprocess.run(["bash", os.path.join(WS, "tools", "ds-balance.sh")],
                                 capture_output=True, text=True, timeout=30).stdout
            return float(out.replace("¥", "").strip().split("（")[0])
        except Exception:
            return None

    def tokens_since(ts_ms):
        try:
            c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True, timeout=10)
            c.execute("pragma busy_timeout=5000")
            ti = to = 0
            for (e,) in c.execute("select event_json from trajectory_runtime_events where created_at > ?", (ts_ms,)):
                if '"model.completed"' not in e:
                    continue
                try:
                    d = json.loads(e)
                except Exception:
                    continue
                u = (d.get("data") or {}).get("usage") or {}
                ti += u.get("input", 0); to += u.get("output", 0)
            c.close()
            return ti, to
        except Exception:
            return 0, 0

    def last_balance():
        try:
            with open(LOG) as f:
                lines = [l for l in f.read().splitlines() if l and not l.startswith("ts,")]
            return float(lines[-1].split(",")[1]) if lines else None
        except Exception:
            return None

    now = int(time.time())
    bal = balance()
    prev = last_balance()
    ti, to = tokens_since((now - INTERVAL) * 1000)
    delta = None if (bal is None or prev is None) else round(bal - prev, 2)
    est = (ti / 1e6) * 2.0 + (to / 1e6) * 3.0

    new = not os.path.exists(LOG) or os.path.getsize(LOG) == 0
    row = "%s,%s,%s,%d,%d,%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), bal, "" if delta is None else delta, ti, to, round(est, 2))
    with open(LOG, "a") as f:
        if new:
            f.write("ts,balance_cny,delta_cny,in_tokens,out_tokens,est_cny\n")
        f.write(row)

    print("bal=%s delta=%s local_in=%d local_out=%d est_cny=%.2f" % (bal, delta, ti, to, est))
    if delta is not None and delta < -1.0 and est < abs(delta) * 0.4:
        print("⚠️ 疑似外部分消费：扣款 %.2f 元，本机同期折算仅 %.2f 元" % (abs(delta), est))
    return 0

if __name__ == "__main__":
    sys.exit(main())
