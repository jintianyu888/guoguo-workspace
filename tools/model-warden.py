#!/usr/bin/env python3
"""model-warden.py — 模型总管
用法:
  probe    串行探活所有云端模型（写 state/model-warden/probe.json）
  local    盘点本地 ollama 实况并与登记表比对
  report   生成管理报告（连接状态 + 经济性 + 分派建议）
"""
import json, os, subprocess, sys, time, fcntl

W = "/home/j/.openclaw/workspace"
MD = os.path.join(W, "state", "model-warden")
REG = os.path.join(MD, "registry.json")
PROBE = os.path.join(MD, "probe.json")
LOCK = os.path.join(MD, ".warden.lock")


def load(p, default=None):
    try:
        return json.load(open(p))
    except Exception:
        return default


def save(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def probe():
    reg = load(REG, {})
    results = {}
    for pname, pv in reg.get("providers", {}).items():
        if pv.get("kind") != "cloud":
            continue
        for mid in (pv.get("models") or {}):
            full = pname + "/" + mid
            t0 = time.time()
            st, out = "FAIL", ""
            try:
                p = subprocess.run(
                    ["openclaw", "infer", "model", "run", "--agent", "main",
                     "--gateway", "--model", full, "--prompt", "回一个字：好"],
                    capture_output=True, text=True, timeout=60)
                o = (p.stdout or "") + (p.stderr or "")
                bad = any(k in o.lower() for k in [
                    "error", "failed", "not found", "401", "403", "429",
                    "no provider", "unavailable"])
                st = "OK" if (p.returncode == 0 and not bad) else "FAIL"
                out = (o.strip().splitlines() or [""])[-1][:60]
            except subprocess.TimeoutExpired:
                st, out = "TIMEOUT", ""
            results[full] = {"status": st, "ms": int((time.time() - t0) * 1000),
                             "snippet": out, "ts": time.strftime("%F %T")}
            print("%-8s %-45s %6dms %s" % (st, full, results[full]["ms"], out), flush=True)
    save(PROBE, {"ts": time.strftime("%F %T"), "results": results})
    ok = sum(1 for v in results.values() if v["status"] == "OK")
    print("")
    print("汇总: %d/%d 可用" % (ok, len(results)))


def local():
    try:
        p = subprocess.run(
            ["curl", "-s", "--max-time", "15", "http://127.0.0.1:11434/api/tags"],
            capture_output=True, text=True, timeout=20)
        tags = json.loads(p.stdout or "{}")
    except Exception as e:
        print("本地 ollama 不可达: %s" % e)
        return
    have = {m.get("name"): round(m.get("size", 0) / 1e9, 1)
            for m in tags.get("models", [])}
    reg = load(REG, {}).get("providers", {}).get("ollama", {}).get("models", {})
    print("=== 本地实际 ===")
    for n, s in sorted(have.items()):
        mark = "已登记" if n in reg else "*** 未登记（新模型）***"
        print("  %-45s %6sGB  %s" % (n, s, mark))
    gone = [n for n in reg if n not in have]
    if gone:
        print("")
        print("=== 登记表有、本地已无 ===")
        for n in gone:
            print("  " + n)
    if any(n not in reg for n in have):
        print("")
        print("结论: 存在未登记新模型，需并入登记表")


def report():
    reg = load(REG, {})
    pr = load(PROBE, {})
    print("=" * 72)
    print("模型总管报告 — " + time.strftime("%F %T"))
    print("=" * 72)
    print("")
    print("【云端】")
    for pname, pv in reg.get("providers", {}).items():
        if pv.get("kind") != "cloud":
            continue
        for mid, mv in (pv.get("models") or {}).items():
            full = pname + "/" + mid
            st = pr.get("results", {}).get(full, {}).get("status", "未探活")
            print("  %-8s %-42s 入¥%-5s 出¥%-5s %s" % (
                st, full, mv.get("in", "?"), mv.get("out", "?"), mv.get("use", "")))
    print("")
    print("【本地】")
    for mid, mv in (reg.get("providers", {}).get("ollama", {}).get("models") or {}).items():
        print("  %-8s %-42s %5sGB %s" % (
            "-", "ollama/" + mid, mv.get("size_gb", "?"), mv.get("use", "")))
    print("")
    print("【经济性】闲时优先本地 > flash；高峰非紧急入队")


def main():
    os.makedirs(MD, exist_ok=True)
    lf = open(LOCK, "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("已有模型总管进程在跑")
        return 3
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    fn = {"probe": probe, "local": local, "report": report}.get(cmd, report)
    fn()
    return 0


if __name__ == "__main__":
    sys.exit(main())
