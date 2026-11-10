#!/usr/bin/env python3
"""work-status.py —— 果果工作状态一览（自动推导，不靠手填）
输出：一行状态 + 在办明细 + 后台作业
状态规则：blocked 有项→🔴阻塞；in_progress 有项→🟡在办；否则🟢空闲
"""
import json, os, subprocess, time, datetime

W = "/home/j/.openclaw/workspace"
F = os.path.join(W, "state", "tasks", "tasks.json")
PATTERNS = ["heartbeat-run.sh", "backup-mirror-verify.sh", "backup-tier1-critical.sh",
            "daily-backup", "store-snapshot.sh", "batch-extract", "eh-mirror.sh", "rsync"]


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def procs():
    out = []
    for p in PATTERNS:
        try:
            r = subprocess.run(["pgrep", "-af", p], capture_output=True, text=True, timeout=3)
            for ln in (r.stdout or "").splitlines():
                if "pgrep" in ln:
                    continue
                out.append((p, ln.strip()[:90]))
        except Exception:
            pass
    # 去重
    seen, uniq = set(), []
    for p, ln in out:
        k = ln.split()[0]
        if k in seen:
            continue
        seen.add(k); uniq.append((p, ln))
    return uniq


def main():
    d = load(F, {})
    pend = []
    def _t(x):
        if isinstance(x, dict): return str(x.get("t") or x.get("title") or x.get("d") or "")
        return str(x)
    _items = d.get("items") or []
    if _items:
        doing = [_t(x) for x in _items if isinstance(x, dict) and x.get("status") in ("in_progress", "doing")]
        _pend = [x for x in _items if isinstance(x, dict) and x.get("status") in ("open", "pending") and not x.get("done_at")]
    else:
        doing = [_t(x) for x in (d.get("in_progress") or [])]
        _pend = d.get("pending") or []
    pend = [_t(x) for x in _pend]
    blocked = [str(x) for x in (d.get("blocked") or [])]
    today = datetime.date.today().isoformat()
    if _items:
        done_today = [x for x in _items if isinstance(x, dict)
                      and str(x.get("done_at") or "")[:10] == today]
    else:
        done_today = [x for x in (d.get("done") or []) if isinstance(x, dict) and str(x.get("d")) == today]
    bg = procs()

    if blocked:
        icon, word = "🔴", "阻塞"
    elif doing:
        icon, word = "🟡", "在办"
    else:
        icon, word = "🟢", "空闲"
    parts = ["%s 果果状态：%s" % (icon, word)]
    if doing:
        parts.append("在办 %d 项｜%s" % (len(doing), "；".join(x[:40] for x in doing[:2])))
    parts.append("待办 %d" % len(pend))
    parts.append("今日完成 %d" % len(done_today))
    parts.append("后台 %d 个" % len(bg))
    print("｜".join(parts))
    for p, ln in bg[:4]:
        print("   · 后台跑：%s" % ln)
    if pend:
        print("   · 接下来：%s" % pend[0][:60])
    if doing:
        print("   · 可打断：否（正在办；急事直接说，我切）")
    else:
        print("   · 可打断：是（空闲，随时派活）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

