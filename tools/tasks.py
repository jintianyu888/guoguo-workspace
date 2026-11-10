#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tasks.py - 果果待办系统（单一数据源，零依赖）
数据: state/tasks/tasks.json (未关闭项) + state/tasks/archive.jsonl (已关闭, 追加)
视图: state/pending-tasks.md (自动生成, 勿手改)
用法: python3 tools/tasks.py <cmd> ; 设计见 docs/待办系统.md
"""
import argparse, json, os, sys, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(BASE, "state", "tasks")
STORE = os.path.join(TDIR, "tasks.json")
ARCHIVE = os.path.join(TDIR, "archive.jsonl")
RENDER = os.path.join(BASE, "state", "pending-tasks.md")
NL = chr(10)
OPEN = ("open", "paused")
CLOSED = ("done", "cancelled")
PRIO = {"P1": 1, "P2": 2, "P3": 3}

def today():
    return datetime.date.today().isoformat()

def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")

def load():
    if not os.path.exists(STORE):
        return {"version": 1, "updated": now(), "items": []}
    with open(STORE, encoding="utf-8") as f:
        return json.load(f)

def save(db):
    db["updated"] = now()
    os.makedirs(TDIR, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORE)

def find(db, tid):
    for it in db["items"]:
        if it.get("id") == tid:
            return it
    return None

def next_id(db):
    d = today().replace("-", "")
    n = 0
    for it in db.get("items", []):
        parts = it.get("id", "").split("-")
        if len(parts) == 3 and parts[1] == d and parts[2].isdigit():
            n = max(n, int(parts[2]))
    return "T-" + d + "-" + str(n + 1).zfill(3)

def archive(it):
    os.makedirs(TDIR, exist_ok=True)
    with open(ARCHIVE, "a", encoding="utf-8") as f:
        f.write(json.dumps(it, ensure_ascii=False) + NL)

def sortkey(it):
    return (PRIO.get(it.get("priority"), 9), it.get("review") or "9999-99-99", it.get("id", ""))

def line(it):
    s = "  - [" + str(it.get("priority", "P?")) + "] " + it.get("id", "") + " " + it.get("title", "")
    tail = []
    if it.get("review"):
        tail.append("复查 " + it["review"])
    if it.get("due"):
        tail.append("截止 " + it["due"])
    if it.get("owner") and it["owner"] != "果果":
        tail.append("归 " + it["owner"])
    if tail:
        s += "  (" + " · ".join(tail) + ")"
    return s

def open_items(db):
    return [i for i in db["items"] if i.get("status") == "open"]

def render(db=None):
    db = db or load()
    op = open_items(db)
    paused = [i for i in db["items"] if i.get("status") == "paused"]
    boss = sorted([i for i in op if i.get("owner") == "主公"], key=sortkey)
    mine = sorted([i for i in op if i.get("owner") != "主公"], key=sortkey)
    L = []
    L.append("# 待办清单（自动生成 · 勿手改；用 tools/tasks.sh 增删改）")
    L.append("")
    L.append("> 更新时间 " + str(db.get("updated", "")) + " · 未完成 " + str(len(op) + len(paused)) + " 项（需主公 " + str(len(boss)) + " · 我在办 " + str(len(mine)) + " · 暂停 " + str(len(paused)) + "）")
    L.append("> 已完成/取消不入本文件（见 state/tasks/archive.jsonl）。数据源 state/tasks/tasks.json，设计见 docs/待办系统.md。")
    L.append("")
    L.append("## 🔴 需主公操作/决策（未完成）")
    L.extend([line(i) for i in boss] or ["  - （无）"])
    L.append("")
    L.append("## 🟡 我在办（未完成）")
    L.extend([line(i) for i in mine] or ["  - （无）"])
    L.append("")
    L.append("## ⏸ 暂停")
    L.extend([line(i) for i in sorted(paused, key=sortkey)] or ["  - （无）"])
    L.append("")
    out = NL.join(L)
    with open(RENDER, "w", encoding="utf-8") as f:
        f.write(out)
    return out

def brief(db=None, limit=5):
    db = db or load()
    boss = sorted([i for i in open_items(db) if i.get("owner") == "主公"], key=sortkey)
    lines = []
    for i in boss[:limit]:
        s = "- [" + str(i.get("priority", "P?")) + "] " + i.get("title", "")
        if i.get("review"):
            s += "（复查 " + i["review"] + "）"
        lines.append(s)
    return NL.join(lines)

def check(db=None):
    db = db or load()
    errs = []
    warns = []
    seen = set()
    for it in db.get("items", []):
        tid = it.get("id", "")
        if not tid:
            errs.append("缺 ID 的条目")
            continue
        if tid in seen:
            errs.append("重复 ID: " + tid)
        seen.add(tid)
        if it.get("status") not in OPEN + CLOSED:
            errs.append(tid + " 状态非法: " + str(it.get("status")))
        if it.get("status") in CLOSED:
            errs.append(tid + " 已关闭却仍在 tasks.json，应归档")
        if not it.get("owner"):
            errs.append(tid + " 缺 owner")
        if not it.get("title"):
            errs.append(tid + " 缺 title")
        for k in ("created", "updated", "review", "due"):
            v = it.get(k)
            if v:
                try:
                    datetime.date.fromisoformat(v)
                except Exception:
                    errs.append(tid + " " + k + " 日期非 YYYY-MM-DD: " + str(v))
        t = it.get("title", "")
        if ("✅" in t) or ("已完成" in t) or ("已解决" in t):
            warns.append(tid + " 标题含完成字样，应 done/cancel 后归档")
        if it.get("status") == "open" and it.get("review") and it["review"] < today():
            warns.append(tid + " 已过复查日 " + it["review"])
    return errs, warns

def main():
    ap = argparse.ArgumentParser(description="果果待办系统")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("add")
    a.add_argument("--title", required=True)
    a.add_argument("--owner", default="果果")
    a.add_argument("--priority", default="P2")
    a.add_argument("--kind", default="action")
    a.add_argument("--detail", default="")
    a.add_argument("--source", default="")
    a.add_argument("--review", default="")
    a.add_argument("--due", default="")
    a.add_argument("--tags", default="")
    a.add_argument("--id", dest="tid", default="")
    for c in ("done", "cancel"):
        p = sub.add_parser(c)
        p.add_argument("id")
        p.add_argument("--reason", default="")
    u = sub.add_parser("update")
    u.add_argument("id")
    for k in ("status", "priority", "review", "owner", "detail", "title", "note"):
        u.add_argument("--" + k, default=None)
    l = sub.add_parser("list")
    l.add_argument("--owner", default=None)
    l.add_argument("--status", default=None)
    l.add_argument("--json", action="store_true")
    sub.add_parser("render")
    sub.add_parser("check")
    b = sub.add_parser("brief")
    b.add_argument("--limit", type=int, default=5)
    sub.add_parser("mine")
    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 1
    if args.cmd == "add":
        db = load()
        it = {"id": args.tid or next_id(db), "title": args.title, "detail": args.detail,
              "status": "open", "owner": args.owner, "priority": args.priority, "kind": args.kind,
              "created": today(), "updated": today(), "review": args.review, "due": args.due,
              "source": args.source, "tags": [x for x in args.tags.split(",") if x],
              "done_at": "", "done_reason": "", "notes": []}
        if find(db, it["id"]):
            print("ID 已存在: " + it["id"], file=sys.stderr)
            return 2
        db["items"].append(it)
        save(db)
        render(db)
        print(it["id"])
        return 0
    if args.cmd in ("done", "cancel"):
        db = load()
        it = find(db, args.id)
        if not it:
            print("找不到: " + args.id, file=sys.stderr)
            return 2
        it["status"] = "done" if args.cmd == "done" else "cancelled"
        it["done_at"] = today()
        it["done_reason"] = args.reason
        it["updated"] = today()
        db["items"] = [x for x in db["items"] if x.get("id") != args.id]
        save(db)
        archive(it)
        render(db)
        print(it["id"] + " -> " + it["status"])
        return 0
    if args.cmd == "update":
        db = load()
        it = find(db, args.id)
        if not it:
            print("找不到: " + args.id, file=sys.stderr)
            return 2
        for k in ("status", "priority", "review", "owner", "detail", "title"):
            v = getattr(args, k)
            if v is not None:
                it[k] = v
        if args.note:
            it.setdefault("notes", []).append(args.note)
        it["updated"] = today()
        save(db)
        render(db)
        print("updated " + it["id"])
        return 0
    if args.cmd == "list":
        db = load()
        items = db["items"]
        if args.owner:
            items = [i for i in items if i.get("owner") == args.owner]
        if args.status:
            items = [i for i in items if i.get("status") == args.status]
        items = sorted(items, key=sortkey)
        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            for i in items:
                print(line(i))
        return 0
    if args.cmd == "render":
        render()
        print("rendered " + RENDER)
        return 0
    if args.cmd == "check":
        errs, warns = check()
        for e in errs:
            print("ERROR " + e)
        for w in warns:
            print("WARN  " + w)
        print("check: " + str(len(errs)) + " errors, " + str(len(warns)) + " warnings")
        return 1 if errs else 0
    if args.cmd == "brief":
        out = brief(limit=args.limit)
        if out:
            print(out)
        return 0
    if args.cmd == "mine":
        for i in sorted([x for x in open_items(load()) if x.get("owner") != "主公"], key=sortkey):
            print(line(i))
        return 0
    return 0

if __name__ == "__main__":
    sys.exit(main())

