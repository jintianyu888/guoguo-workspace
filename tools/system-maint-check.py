#!/usr/bin/env python3
"""system-maint-check.py v0.1 — 系统维护项自检（全只读，不动配置、不跑修复）
检查：①版本/是否有新版 ②遗留升级记录 ③插件数据迁移未完成 ④systemd 失败单元
     ⑤网关内存 vs 上限 ⑥根盘空间
输出：stdout 摘要 + state/sysmaint/report-<ts>.json
退出码：0 正常；1 有 P1 及以上（供上层判断）
"""
import json, os, re, subprocess, sys
from datetime import datetime

WS = "/home/j/.openclaw/workspace"
OUT = WS + "/state/sysmaint"

def run(cmd, t=45):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t)
        return (p.returncode, (p.stdout or "") + (p.stderr or ""))
    except Exception as e:
        return (124, "timeout/err: %s" % e)

def main():
    findings = []  # (level, text)
    now = datetime.now()
    # 1) 版本
    rc, out = run("openclaw --version", 30)
    ver = (out.strip().splitlines() or ["?"])[0] if rc == 0 else "读取失败"
    findings.append(("info", "当前版本：%s" % ver))
    # 2) 遗留升级记录
    hits = []
    for root in (os.path.expanduser("~/.openclaw/state"), os.path.expanduser("~/.openclaw")):
        for dirpath, dirnames, filenames in os.walk(root):
            if dirpath.count(os.sep) - root.count(os.sep) > 2:
                dirnames[:] = []
                continue
            for fn in filenames:
                if re.search(r"(update|upgrade).*(history|pending|state)", fn, re.I):
                    hits.append(os.path.join(dirpath, fn))
    if hits:
        findings.append(("p2", "发现升级记录文件 %d 个（需确认是否有遗留未完成项）" % len(hits)))
    # 3) 插件迁移未完成（memory-lancedb 等）
    rc, out = run("grep -rl 'migration' ~/.openclaw/logs 2>/dev/null | head -3", 20)
    if "migration" in out and re.search(r"(pending|incomplete|failed)", out, re.I):
        findings.append(("p2", "插件数据迁移疑似未完成（日志有 migration 关键字）"))
    # 4) systemd 失败单元
    rc, out = run("systemctl --user --failed --no-legend --no-pager 2>/dev/null", 30)
    failed = [l for l in out.splitlines() if l.strip()]
    if failed:
        findings.append(("p1", "systemd 失败单元 %d 个：%s" % (len(failed), "; ".join(f.split()[0] for f in failed[:3]))))
    # 5) 网关内存（以 systemd 实际软/硬限为基准，不再写死 4G）
    rc, out = run("pgrep -f 'openclaw.*gateway' | head -1", 15)
    pid = out.strip().splitlines()[0].strip() if out.strip() else ""
    rss_mb = None
    if pid.isdigit():
        try:
            with open("/proc/%s/status" % pid) as f:
                for ln in f:
                    if ln.startswith("VmRSS:"):
                        rss_mb = int(ln.split()[1]) // 1024
        except Exception:
            pass
    lim_mb, hard_mb = 8192, 12288
    rc, out = run("systemctl --user show openclaw-gateway -p MemoryHigh -p MemoryMax", 20)
    for ln in out.splitlines():
        if ln.startswith("MemoryHigh=") and ln.split("=", 1)[1].strip().isdigit():
            v = int(ln.split("=", 1)[1])
            if v > 0: lim_mb = v // (1024 * 1024)
        if ln.startswith("MemoryMax=") and ln.split("=", 1)[1].strip().isdigit():
            v = int(ln.split("=", 1)[1])
            if v > 0: hard_mb = v // (1024 * 1024)
    if rss_mb:
        pct = rss_mb * 100 // hard_mb if hard_mb else 0
        if rss_mb > lim_mb * 0.95:
            findings.append(("p1", "网关内存 %dMB 已达软限 %dMB 的 %d%%（硬限 %dMB）" % (rss_mb, lim_mb, rss_mb * 100 // lim_mb, hard_mb)))
        elif rss_mb > lim_mb * 0.85:
            findings.append(("p2", "网关内存 %dMB 接近软限 %dMB（%d%%，硬限 %dMB）" % (rss_mb, lim_mb, rss_mb * 100 // lim_mb, hard_mb)))
        else:
            findings.append(("info", "网关内存 %dMB / 软限 %dMB / 硬限 %dMB（%d%%）" % (rss_mb, lim_mb, hard_mb, pct)))
    # 6) 根盘
    rc, out = run("df -P / | tail -1", 15)
    try:
        pct = int(out.split()[4].rstrip("%"))
        if pct >= 88:
            findings.append(("p1", "根盘使用率 %d%%" % pct))
        else:
            findings.append(("info", "根盘使用率 %d%%" % pct))
    except Exception:
        pass

    os.makedirs(OUT, exist_ok=True)
    ts = now.strftime("%Y%m%d-%H%M")
    rep = {"checked_at": now.isoformat(timespec="seconds"),
           "findings": [{"level": l, "text": t} for l, t in findings]}
    with open("%s/report-%s.json" % (OUT, ts), "w") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    for l, t in findings:
        print("[%s] %s" % (l, t))
    return 1 if any(l in ("p0", "p1") for l, _ in findings) else 0

if __name__ == "__main__":
    sys.exit(main())
