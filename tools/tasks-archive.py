#!/usr/bin/env python3
"""tasks-archive.py — 陈旧台账归档 v2 (2026-10-25)

规则（v2 按双审收紧）：
  - 只归档 status == "open"（与 tasks-footer.py 口径一致；pending/待拍板不动）
  - owner 必须显式存在且 != 主公（owner 缺失一律跳过，需 --include-unknown-owner 才纳入）
  - 标题不含「待拍板」
  - updated/created 早于 --days 天（默认 7），时间解析失败一律跳过
  - 写锁 flock，写前备份，写后原子替换，archive.jsonl 记 batch_id 便于回滚
默认 dry-run；--apply 才执行。
"""
import argparse, fcntl, json, os, shutil, sys, datetime

W = "/home/j/.openclaw/workspace"
F = os.path.join(W, "state", "tasks", "tasks.json")
A = os.path.join(W, "state", "tasks", "archive.jsonl")
LOCK = F + ".lock"

def parse_ts(s):
    """逐候选字段解析；支持带时区。返回 tz-aware datetime 或 None。"""
    if not s: return None
    s = str(s).strip().replace("T", " ")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.replace(tzinfo=datetime.timezone.utc)
        except Exception: pass
    return None

def item_ts(it):
    for k in ("updated", "created", "done"):
        v = parse_ts(it.get(k))
        if v: return v
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--include-unknown-owner", action="store_true")
    a = ap.parse_args()

    lf = open(LOCK, "w")
    try: fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        print("另一个归档进程在跑（锁占用），退出"); return 5

    d = json.load(open(F, encoding="utf-8"))
    items = d["items"] if isinstance(d, dict) else d
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=a.days)
    keep, move, skipped_ts = [], [], 0
    for it in items:
        if not isinstance(it, dict):
            keep.append(it); continue
        title = str(it.get("title") or "")
        owner = it.get("owner")
        ts = item_ts(it)
        owner_ok = (owner not in (None, "", "主公")) or (a.include_unknown_owner and owner != "主公")
        if it.get("status") == "open" and owner_ok and "待拍板" not in title and ts is not None:
            if ts < cutoff:
                move.append(it); continue
        elif it.get("status") == "open" and ts is None:
            skipped_ts += 1
        keep.append(it)

    print("总计 %d | 保留 %d | 归档 %d | 时间不可解析跳过 %d（阈值 %d 天）" % (len(items), len(keep), len(move), skipped_ts, a.days))
    for it in move[:20]:
        print("  -", str(it.get("id"))[:20], str(it.get("title"))[:44])

    if not move:
        print("无可归档项"); return 0
    if not a.apply:
        print("dry-run，未改动。加 --apply 执行。"); return 0

    batch = datetime.datetime.now().strftime("arch-%Y%m%d-%H%M%S")
    bak = F + ".bak-archive-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    shutil.copy2(F, bak)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(A, "a", encoding="utf-8") as f:
        for it in move:
            rec = dict(it)
            rec["archived_at"] = now
            rec["archive_batch"] = batch
            rec["archive_reason"] = "stale-%dd" % a.days
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out = dict(d) if isinstance(d, dict) else {}
    out["items"] = keep
    out["updated"] = now
    tmp = F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, F)
    print("已归档 %d 项 -> %s（batch=%s，备份 %s）" % (len(move), A, batch, bak))
    print("回滚方式：")
    print("  1) cp %s %s" % (bak, F))
    print("  2) 从 %s 删除 archive_batch == %s 的行" % (A, batch))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
