#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日全量盘点 tools/daily-inventory.py
脚本全量导出台账，模型不读全文；带完整性校验。
用法: daily-inventory.py            # 导出
     daily-inventory.py --summary    # 只打印摘要（给模型看）
"""
import os, sys, json, sqlite3, datetime, collections

WS = "/home/j/.openclaw/workspace"
DB = os.path.join(WS, "state/ledger/ledger.db")
OPEN = ("pending", "open", "in_progress", "paused", "quarantine")

def main():
    today = datetime.date.today()
    if not os.path.exists(DB):
        print("ERR 台账不存在"); return 2
    c = sqlite3.connect(DB); cur = c.cursor()
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status IN (%s)" % ",".join("?"*len(OPEN)), OPEN)
    total = cur.fetchone()[0]
    cur.execute("SELECT task_id,title,status,assignee,verify_cmd FROM tasks WHERE status IN (%s) ORDER BY status, task_id" % ",".join("?"*len(OPEN)), OPEN)
    rows = cur.fetchall()
    if len(rows) != total:
        print("FAIL 盘点不完整：导出 %d 条，台账 %d 条" % (len(rows), total)); return 1
    outdir = os.path.join(WS, "state/work")
    os.makedirs(outdir, exist_ok=True)
    md = os.path.join(outdir, "daily-inventory-%s.md" % today.strftime("%Y%m%d"))
    js = os.path.join(outdir, "daily-inventory-%s.json" % today.strftime("%Y%m%d"))
    with open(js, "w", encoding="utf-8") as f:
        json.dump([{"id": r[0], "title": r[1], "status": r[2], "assignee": r[3], "verify": r[4]} for r in rows], f, ensure_ascii=False, indent=1)
    stat = collections.Counter(r[2] for r in rows)
    noverify = sum(1 for r in rows if not r[4])
    with open(md, "w", encoding="utf-8") as f:
        f.write("# 每日全量盘点 %s\n\n" % today.strftime("%Y-%m-%d"))
        f.write("总条数 %d｜缺验收口径 %d 条\n\n" % (len(rows), noverify))
        for st in OPEN:
            sub = [r for r in rows if r[2] == st]
            if not sub: continue
            f.write("## %s（%d）\n" % (st, len(sub)))
            for r in sub:
                f.write("- #%s %s ［验:%s］\n" % (r[0], str(r[1])[:70], "有" if r[4] else "无"))
            f.write("\n")
    print("总条数 %d ｜ 缺验收口径 %d" % (len(rows), noverify))
    print("状态: " + " ".join("%s=%d" % (k, stat[k]) for k in OPEN if stat[k]))
    print("清单: " + md)
    print("JSON: " + js)
    return 0

if __name__ == "__main__":
    sys.exit(main())