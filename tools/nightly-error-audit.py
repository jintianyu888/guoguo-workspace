#!/usr/bin/env python3
"""nightly-error-audit.py — 每夜错误自动分析（零 token）
用 journalctl -o json 取完整（多行）日志条目 → 归一化签名 → 与基线比对 →
分离「计划内(断网窗口等)」与「新问题」；有新问题才打印报告（供 announce 投递）。
用法: nightly-error-audit.py [--hours 24] [--always] [--unit openclaw-gateway.service]
台账: state/nightly-error-audit.log  基线: state/nightly-error-baseline.json
"""
import os, re, json, sys, subprocess, datetime, argparse

W = "/home/j/.openclaw/workspace"
BASE = os.path.join(W, "state", "nightly-error-baseline.json")
LOG = os.path.join(W, "state", "nightly-error-audit.log")


def rotate_log(path=LOG, max_bytes=5 * 1024 * 1024, keep_lines=3000):
    """台账超过 5MB 就轮转：全量留 .1.gz，正文只留最近 3000 行（2026-11-09 加）"""
    try:
        if not os.path.exists(path) or os.path.getsize(path) <= max_bytes:
            return
        import gzip
        with open(path, "rb") as f:
            data = f.read()
        with gzip.open(path + ".1.gz", "wb") as g:
            g.write(data)
        tail = data.decode("utf-8", "replace").splitlines()[-keep_lines:]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(tail) + "\n")
    except Exception:
        pass


DEFAULT_BASE = {
    "note": "已知/计划内错误签名（定时断网窗口等），不计为「新问题」",
    "signatures": [
        r"timeout of \d+ms exceeded",
        r"AxiosError",
        r"bot info probe timed out",
        r"getaddrinfo\(\) failed",
        r"obtain-openid",
        r"memory pressure: level=warning",
        r"\[feishu\].*timed out",
        r"CheckConnection",
        r"streaming start failed; using non-streaming",
    ],
    "quiet_hours": ["04:00", "06:00"],
}

def load_base():
    try:
        d = json.load(open(BASE, encoding="utf-8"))
        d.setdefault("signatures", DEFAULT_BASE["signatures"])
        d.setdefault("quiet_hours", DEFAULT_BASE["quiet_hours"])
        return d
    except Exception:
        return dict(DEFAULT_BASE)

def norm(s):
    s = re.sub(r"\d{4}-\d{2}-\d{2}T[\d:.+\-]+", "", s)
    s = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{8,}\b", "<id>", s)
    s = re.sub(r"\d+", "N", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:180]

def collect(unit, hours):
    """返回 [(hour, message), ...]"""
    since = (datetime.datetime.now() - datetime.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")
    cmd = ["journalctl", "--user", "-u", unit, "--since", since, "--no-pager", "-o", "json"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=90).stdout
    except Exception:
        out = ""
    recs = []
    for ln in out.splitlines():
        try:
            j = json.loads(ln)
        except Exception:
            continue
        msg = j.get("MESSAGE", "")
        if isinstance(msg, (list, tuple)):
            msg = " ".join(str(x) for x in msg)
        if not isinstance(msg, str):
            continue
        if not re.search(r"(error|fatal|timeout|failed|异常|🔴|❌)", msg, re.I):
            continue
        h = "??"
        try:
            us = int(j.get("__REALTIME_TIMESTAMP", 0)) / 1e6
            h = datetime.datetime.fromtimestamp(us).strftime("%H")
        except Exception:
            pass
        recs.append((h, msg.strip()))
    return recs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--always", action="store_true")
    ap.add_argument("--unit", default="openclaw-gateway.service")
    a = ap.parse_args()

    base = load_base()
    sigs = [re.compile(p, re.I) for p in base["signatures"]]
    qa, qb = base["quiet_hours"]

    recs = collect(a.unit, a.hours)
    by_sig, by_hour = {}, {}
    for h, msg in recs:
        by_hour[h] = by_hour.get(h, 0) + 1
        d = by_sig.setdefault(norm(msg), {"n": 0, "full": msg, "hours": set()})
        d["n"] += 1
        d["hours"].add(h)

    def expected(entry):
        if any(s.search(entry["full"]) for s in sigs):
            return True
        hs = [x for x in entry["hours"] if x != "??"]
        return bool(hs) and all(qa[:2] <= x <= qb[:2] for x in hs)

    exp_n = new_n = 0
    new = {}
    for k, v in by_sig.items():
        if expected(v):
            exp_n += v["n"]
        else:
            new_n += v["n"]
            new[k] = v

    ts = datetime.datetime.now().strftime("%F %T")
    rotate_log()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("[%s] 近%dh 错误条 %d ｜ 计划内 %d ｜ 新问题 %d/%d 类 ｜ 小时 %s\n"
                % (ts, a.hours, len(recs), exp_n, new_n, len(new),
                   " ".join("%s:%d" % (h, by_hour[h]) for h in sorted(by_hour))))
        for k, v in sorted(new.items(), key=lambda x: -x[1]["n"]):
            f.write("  NEW x%d %s :: %s\n" % (v["n"], sorted(v["hours"]), v["full"][:220]))

    if new or a.always:
        out = ["🕵️【每夜错误分析】" + datetime.datetime.now().strftime("%m-%d %H:%M")]
        out.append("① 近 %d 小时共 %d 条错误；计划内（断网窗口 04–06 等）%d 条 → 已识别不折腾" % (a.hours, len(recs), exp_n))
        if new:
            out.append("② 新/需处理：%d 条 / %d 类" % (new_n, len(new)))
            for k, v in sorted(new.items(), key=lambda x: -x[1]["n"])[:8]:
                out.append("   · x%d 时段%s：%s" % (v["n"], sorted(v["hours"]), v["full"][:150]))
            out.append("—— 我会按签名定位来源并处置/给方案")
        else:
            out.append("② 新问题：无 ✅")
        print("\n".join(out))
    return 0

if __name__ == "__main__":
    sys.exit(main())
