#!/usr/bin/env python3
"""tasks-audit.py — 台账保洁：状态校验 / 自动归档 / 陈旧标记
用法: python3 tools/tasks-audit.py [--fix] [--json]
规则:
  - 状态白名单 pending|in_progress|paused|done|cancelled；非法值按完成痕迹归位并记账
  - done 且 done_at 超 ARCHIVE_DAYS(30) 天 -> 移入 state/tasks/archive/YYYY-MM.json
  - pending/in_progress 超 STALE_DAYS(14) 天无更新 -> stale=true（页脚只计数不逐条播报）
  - 标题为 dict 时归一为字符串
退出码恒 0（仅内部错误返回 3），异常通过文字报告由调用方决定是否告警。
"""
import json, os, sys, datetime, collections

W = "/home/j/.openclaw/workspace"
F = os.path.join(W, "state", "tasks", "tasks.json")
ARCH = os.path.join(W, "state", "tasks", "archive")
OK_STATUS = {"pending", "in_progress", "paused", "done", "cancelled"}
ARCHIVE_DAYS = 30
STALE_DAYS = 14


def load():
    with open(F, encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, list):
        d = {"items": d}
    return d


def save(d):
    tmp = F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, F)


def day(v):
    s = str(v or "")[:10]
    try:
        return datetime.date.fromisoformat(s)
    except Exception:
        return None


def main():
    import fcntl
    lf = open(os.path.join(W, "state", "tasks", ".audit.lock"), "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("台账体检：已有实例在跑，跳过本轮")
        return 0
    fix = "--fix" in sys.argv
    as_json = "--json" in sys.argv
    d = load()
    items = d.get("items") or []
    today = datetime.date.today()
    report = {"illegal": [], "archived": 0, "stale": 0, "normalized_title": 0}

    # 1. 状态校验 + 标题归一
    for i in items:
        if not isinstance(i, dict):
            continue
        if isinstance(i.get("title"), dict):
            t = i["title"]
            i["title"] = str(t.get("t") or t.get("title") or t.get("name") or "")
            report["normalized_title"] += 1
        st = i.get("status")
        if st not in OK_STATUS:
            # 评审必改1：非法状态只隔离，不自动映射到活动态（避免复活/误隐藏）
            i["audit_prev_status"] = st
            i["status"] = "quarantine"
            report["illegal"].append({"no": i.get("no"), "from": st, "to": "quarantine"})
            if fix:
                i["note"] = ((i.get("note") or "") + "｜audit隔离:非法状态%s" % st).strip("｜")

    # 2. 陈旧标记
    for i in items:
        if not isinstance(i, dict):
            continue
        if i.get("status") in ("pending", "in_progress"):
            u = day(i.get("updated"))
            should = bool(u and (today - u).days >= STALE_DAYS and not i.get("priority"))
            if should and not i.get("stale"):
                report["stale"] += 1
            if fix:
                if should:
                    i["stale"] = True
                elif i.get("stale"):
                    i.pop("stale", None)  # 有更新即自动解除，可逆

    # 3. 归档
    keep, move = [], []
    for i in items:
        if isinstance(i, dict) and i.get("status") in ("done", "cancelled"):
            dt = day(i.get("done_at"))
            has_ev = bool(i.get("done_at") and i.get("done_reason"))
            if has_ev and dt and (today - dt).days >= ARCHIVE_DAYS and not i.get("reopened"):
                move.append(i); continue
            elif i.get("status") in ("done", "cancelled") and not has_ev:
                report["no_evidence"] = report.get("no_evidence", 0) + 1
        keep.append(i)
    if fix and move:
        os.makedirs(ARCH, exist_ok=True)
        bymonth = collections.defaultdict(list)
        for i in move:
            dt = day(i.get("done_at")) or day(i.get("date")) or today
            bymonth[dt.strftime("%Y-%m")].append(i)
        for m, rows in bymonth.items():
            p = os.path.join(ARCH, m + ".json")
            old = []
            if os.path.exists(p):
                try:
                    old = json.load(open(p, encoding="utf-8"))
                    if isinstance(old, dict):
                        old = old.get("items") or []
                except Exception:
                    old = []
            with open(p + ".tmp", "w", encoding="utf-8") as f:
                json.dump(old + rows, f, ensure_ascii=False, indent=1)
            os.replace(p + ".tmp", p)
        d["items"] = keep
        report["archived"] = len(move)
    elif move:
        report["archived"] = len(move)

    if fix:
        save(d)

    cnt = collections.Counter(i.get("status") for i in items if isinstance(i, dict))
    if as_json:
        print(json.dumps({"report": report, "status": dict(cnt), "total": len(keep)}, ensure_ascii=False))
    else:
        print("台账体检：总数 %d｜%s" % (len(keep), " ".join("%s=%d" % (k, v) for k, v in cnt.items())))
        if report["illegal"]:
            print("  非法状态 %d 条（%s）" % (len(report["illegal"]), "已归一" if fix else "未处理"))
        if report["stale"]:
            print("  新增陈旧 %d 条（>%d 天）" % (report["stale"], STALE_DAYS))
        _st = [i for i in keep if isinstance(i, dict) and i.get("stale")]
        if _st:
            print("  陈旧清单 %d 条（需分诊，不只报数）：" % len(_st))
            for i in _st[:15]:
                print("    - [%s] %s" % (i.get("no"), str(i.get("title") or "")[:56]))
        if report["archived"]:
            print("  归档 %d 条（done >%d 天）%s" % (report["archived"], ARCHIVE_DAYS, "" if fix else " [dry-run]"))
        if not (report["illegal"] or report["stale"] or report["archived"]):
            print("  一切正常")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        print("AUDIT_ERROR: %s" % e)
        raise SystemExit(3)
