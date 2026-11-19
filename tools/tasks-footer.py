#!/usr/bin/env python3
"""tasks-footer.py v3 (2026-10-18) - 任务区唯一渲染器
数据源: state/tasks/tasks.json
规则:
  - open 且无完成痕迹 = 待办; >STALE_DAYS 天未更新 -> 陈旧(仅计数)
  - 有完成痕迹(done_at/done_reason/completed)或标题含完成字样 -> 疑似已完成(不播报)
  - 排序按 updated/created 降序(新项优先)
  - --brief 模式带内容去重: 与上次一致只报计数
"""
import hashlib, json, os, sys, datetime

W = "/home/j/.openclaw/workspace"
F = os.path.join(W, "state", "tasks", "tasks.json")
HASHF = os.path.join(W, "state", "brief-hash.json")
STALE_DAYS = int(os.environ.get("TASKS_STALE_DAYS", "10"))
MAXE = int(os.environ.get("TASKS_MAX", "4"))
NL = chr(10)


def load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def day(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def suspect(it):
    if it.get("done_at") or it.get("done_reason") or it.get("completed"):
        return True
    t = str(it.get("title") or "")
    for k in ("已完成", "已修复", "已跑通", "已关闭", "已上线"):
        if k in t:
            return True
    return False


def numpfx(x):
    n = x.get("no")
    return ("[%s] " % n) if isinstance(n, int) and n > 0 else ""


def ensure_no(items):
    mx = 0
    for x in items:
        n = x.get("no")
        if isinstance(n, int) and n > mx:
            mx = n
    changed = False
    for x in items:
        n = x.get("no")
        if not (isinstance(n, int) and n > 0):
            mx += 1
            x["no"] = mx
            changed = True
    if changed:
        try:
            d = load(F, {})
            d["items"] = items
            tmp = F + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, F)
        except Exception:
            pass
    return items


def build():
    d = load(F, {})
    raw = d.get("items") or []
    norm = []
    for x in raw:
        if isinstance(x, str):
            norm.append({"title": x, "status": "quarantine"})
        elif isinstance(x, dict):
            y = dict(x)
            if not y.get("title"):
                y["title"] = y.get("t") or y.get("name") or y.get("desc") or ""
            y["title"] = str(y.get("title") or "")
            norm.append(y)
    items = ensure_no(norm)
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=STALE_DAYS)

    def recency(x):
        return max(str(x.get("updated") or ""), str(x.get("created") or ""))

    def fresh(it):
        u = day(it.get("updated")) or day(it.get("created"))
        return (u is None) or (u >= cutoff) or (it.get("priority") in ("P0", "P1"))

    op_raw = [x for x in items if x.get("status") in ("open", "pending")]
    sus = [x for x in op_raw if suspect(x)]
    op = [x for x in op_raw if not suspect(x)]
    doing_all = [x for x in items if x.get("status") in ("in_progress", "doing")]
    doing = [x for x in doing_all if fresh(x)]
    doing_stale = [x for x in doing_all if not fresh(x)]
    # 2026-11-08 修：导出视图没有 done_at，导致「今日完成」永远 0
    done_today = [x for x in items if x.get("status") == "done" and str(x.get("updated") or "")[:10] == today.isoformat()]
    fresh_open = [x for x in op if fresh(x)]
    stale = [x for x in op if not fresh(x)]
    fresh_open.sort(key=recency, reverse=True)
    boss = [x for x in fresh_open if x.get("owner") == "主公"]
    mine = [x for x in fresh_open if x.get("owner") != "主公"]
    return boss, mine, doing, done_today, stale, sus, doing_stale


def main():
    brief = "--brief" in sys.argv
    boss, mine, doing, done_today, stale, sus, doing_stale = build()
    summary = "待办 %d | 在办 %d | 今日完成 %d | 陈旧 %d" % (
        len(boss) + len(mine), len(doing), len(done_today), len(stale))
    lines = []
    if brief:
        lines.append("【需主公拍板】%d 项" % len(boss))
    else:
        lines.append("📋 待办 %d 项（陈旧 %d 项已折叠）" % (len(boss) + len(mine), len(stale)))
    for x in boss[:MAXE]:
        lines.append("   • " + numpfx(x) + (x.get("title") or "")[:70])
    if len(boss) > MAXE:
        lines.append("   …另有 %d 项等你拍板" % (len(boss) - MAXE))
    if mine:
        _today = datetime.date.today()
        def _age(x):
            u = day(x.get("updated")) or day(x.get("created"))
            return max(0, (_today - u).days) if u else 0
        def _tag(x):
            a = _age(x)
            return numpfx(x) + (("[%dd]" % a) if a >= 3 else "") + (x.get("title") or "")[:26]
        shown = mine[:4]
        more = ("  …另有 %d 项" % (len(mine) - len(shown))) if len(mine) > len(shown) else ""
        lines.append("   果果待办 %d 项：%s%s" % (len(mine), "；".join(_tag(x) for x in shown), more))
    lines.append("🔄 在办 %d 项" % len(doing))
    for x in doing[:MAXE]:
        lines.append("   • " + numpfx(x) + (x.get("title") or "")[:70])
    lines.append("✅ 今日完成 %d 项" % len(done_today))
    if stale or doing_stale:
        lines.append("⏳ 陈旧待核实 %d 项（>%d 天未更新，问『陈旧待办』列出）" % (len(stale) + len(doing_stale), STALE_DAYS))
    if sus:
        lines.append("⚠️ 疑似已完成待关闭 %d 项（不进入播报；问『待关闭』列出）" % len(sus))

    body = NL.join(lines).strip()
    if brief:
        h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        prev = load(HASHF, {})
        try:
            with open(HASHF, "w", encoding="utf-8") as f:
                json.dump({"hash": h, "date": datetime.date.today().isoformat()}, f)
        except Exception:
            pass
        if isinstance(prev, dict) and prev.get("hash") == h:
            body = summary + "（与上次一致，明细未变）"
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
