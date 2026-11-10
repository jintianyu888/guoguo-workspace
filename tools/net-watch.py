#!/usr/bin/env python3
import sys as _qsys
_qsys.path.insert(0, "/home/j/.openclaw/workspace/tools")
try:
    from quiet_window import in_quiet_window as _qiw
    if _qiw():
        _qsys.exit(0)
except Exception:
    pass
"""网络探针（含断网类型判定）。纯标准库，零 API 成本。

用法：
  net-watch.py                      # 夜间模式：默认采 150 分钟、每 20 秒一次
  net-watch.py --minutes 150 --interval 20
  net-watch.py --quick              # 单次采样（供全天巡检用），只在异常时留痕

断网类型判定（关键：区分「谁来背锅」）：
  A 整体断网    路由器(192.168.1.1)都连不上 → 换 DNS 也没用（如路由器重启）
  B DNS 解析失败 路由器活着，但解析不了 → **备用 DNS 可解**
  C 出口/上游抖动 DNS 能解析，但连不上外网 → 等恢复 / 重试
  D 单服务故障   仅某个服务不可达 → 与我们无关

输出：
  state/net-outage-YYYY-MM-DD.json   完整采样 + 断网区间（含类型）
  state/net-outage.log               一行摘要（追加）
"""
import argparse, json, os, socket, time, datetime

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(WS, "state")

DNS_HOSTS = ["open.feishu.cn", "api.deepseek.com"]
ROUTER = ("192.168.1.1", 80)              # 路由器是否活着（LAN 视角）
SERVICES = [("open.feishu.cn", 443), ("api.deepseek.com", 443)]


def dns_ok(host, timeout=2.0):
    try:
        old = socket.getdefaulttimeout(); socket.setdefaulttimeout(timeout)
        socket.getaddrinfo(host, None)
        return True
    except Exception:
        return False
    finally:
        socket.setdefaulttimeout(old)


def tcp_ok(host, port, timeout=2.0):
    s = None
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        return True
    except Exception:
        return False
    finally:
        if s:
            try: s.close()
            except Exception: pass


def sample():
    d = {h: dns_ok(h) for h in DNS_HOSTS}
    t = {f"{h}:{p}": tcp_ok(h, p) for h, p in SERVICES}
    router_ok = tcp_ok(*ROUTER)
    dns_all = any(d.values())
    out_ok = dns_all and any(t.values())
    return {"dns": d, "tcp": t, "router_ok": router_ok, "dns_ok": dns_all, "out_ok": bool(out_ok)}


def classify(seg):
    """seg: 断网区间的采样列表 → 类型标签"""
    router = any(r.get("router_ok") for r in seg)
    dns = any(r.get("dns_ok") for r in seg)
    if not router:
        return "A 整体断网（路由器/LAN 不可达）→ 换DNS无用"
    if not dns:
        return "B DNS解析失败（路由器活着）→ 备用DNS可解"
    return "C 出口/上游抖动（DNS通、连不上外网）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=150.0)
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--quick", action="store_true", help="单次采样，仅异常时留痕")
    a = ap.parse_args()

    os.makedirs(STATE, exist_ok=True)
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    logpath = os.path.join(STATE, "net-outage.log")

    # ---------- 快速模式：全天巡检用 ----------
    if a.quick:
        s = sample()
        if not s["out_ok"]:
            rtype = classify([s])
            line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} 异常：{rtype} (router={'OK' if s['router_ok'] else 'NG'} dns={'OK' if s['dns_ok'] else 'NG'})"
            with open(logpath, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            print(line)
        return 0

    # ---------- 连续采样模式 ----------
    t0 = time.time()
    rows = []
    while time.time() - t0 < a.minutes * 60:
        s = sample()
        rows.append({"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **s})
        time.sleep(max(1.0, a.interval))

    outages, cur = [], None
    for r in rows:
        if not r["out_ok"]:
            if cur is None:
                cur = {"start": r["ts"], "end": r["ts"], "samples": 1, "_seg": [r]}
            else:
                cur["end"] = r["ts"]; cur["samples"] += 1; cur["_seg"].append(r)
        elif cur is not None:
            cur["type"] = classify(cur.pop("_seg")); outages.append(cur); cur = None
    if cur is not None:
        cur["type"] = classify(cur.pop("_seg")); outages.append(cur)

    bad = sum(1 for r in rows if not r["out_ok"])
    result = {
        "date": date,
        "started": rows[0]["ts"] if rows else None,
        "ended": rows[-1]["ts"] if rows else None,
        "samples": len(rows),
        "failed_samples": bad,
        "fail_ratio": round(bad / max(1, len(rows)), 3),
        "outages": outages,
        "interval_s": a.interval,
    }
    with open(os.path.join(STATE, f"net-outage-{date}.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    if outages:
        spans = "; ".join(f"{o['start'][11:]}→{o['end'][11:]} [{o['type']}]" for o in outages)
        line = f"{date} 断网 {len(outages)} 段：{spans}（失败率 {result['fail_ratio']*100:.1f}%）"
    else:
        line = f"{date} 未检出断网（采样 {len(rows)} 次，失败率 {result['fail_ratio']*100:.1f}%）"

    with open(logpath, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
