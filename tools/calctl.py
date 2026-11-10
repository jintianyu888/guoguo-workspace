#!/usr/bin/env python3
"""calendar.py —— 统一日历真源唯一写入口（2026-11-07 主公令，双审通过 v1.1）
存储：state/calendar/events.db 表 events
规则：时间半开区间 [start,end)；冲突=同一 owner 或 同一 place 且时间重叠；冲突即拒绝，不静默覆盖
"""
import argparse, datetime as dt, json, os, sqlite3, sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(W, "state/calendar/events.db")

SCHEMA = """
create table if not exists events(
  id integer primary key autoincrement,
  ts_start text not null, ts_end text not null,
  title text not null, owner text default '', agent text default '',
  place text default '', kind text default 'event',
  source_ref text default '', status text default 'active',
  created text default '', updated text default ''
);
create index if not exists idx_events_time on events(ts_start, ts_end);
"""

def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=5); c.row_factory = sqlite3.Row
    c.execute("pragma busy_timeout=5000")
    c.executescript(SCHEMA); return c

def now(): return dt.datetime.now().astimezone().isoformat(timespec="minutes")

def conflicts(c, s, e, owner, place, exclude=None):
    q = "select * from events where status='active' and ts_start<? and ts_end>?"
    args = [e, s]
    if exclude: q += " and id!=?"; args.append(exclude)
    out = []
    for r in c.execute(q, args):
        if (owner and r["owner"] == owner) or (place and r["place"] == place):
            out.append(dict(r))
    return out

def cmd_add(a):
    c = conn()
    c.isolation_level = None
    c.execute("begin immediate")
    cf = conflicts(c, a.start, a.end, a.owner, a.place)
    if cf and not a.force:
        c.execute("rollback")
        print("冲突：" + json.dumps(cf, ensure_ascii=False))
        return 1
    cur = c.execute("insert into events(ts_start,ts_end,title,owner,agent,place,kind,source_ref,created,updated) values(?,?,?,?,?,?,?,?,?,?)",
                    (a.start, a.end, a.title, a.owner, a.agent, a.place, a.kind, a.source_ref, now(), now()))
    c.execute("commit"); print("ADDED %d %s %s~%s" % (cur.lastrowid, a.title, a.start, a.end)); return 0

def cmd_list(a):
    c = conn(); q = "select * from events where status='active'"; args = []
    if a.since: q += " and ts_end>=?"; args.append(a.since)
    if a.until: q += " and ts_start<=?"; args.append(a.until)
    if a.owner: q += " and owner=?"; args.append(a.owner)
    q += " order by ts_start"
    rows = [dict(r) for r in c.execute(q, args)]
    if a.json: print(json.dumps(rows, ensure_ascii=False, indent=1)); return 0
    for r in rows:
        print("#%d %s %s~%s %s%s" % (r["id"], r["title"], r["ts_start"], r["ts_end"],
              ("@" + r["place"] + " ") if r["place"] else "", r["owner"]))
    if not rows: print("（无日程）")
    return 0

def cmd_move(a):
    c = conn()
    c.isolation_level = None
    c.execute("begin immediate")
    row = c.execute("select * from events where id=? and status='active'", (a.id,)).fetchone()
    if not row:
        c.execute("rollback"); print("无此事件 #%d" % a.id); return 1
    s = a.start or row["ts_start"]; e = a.end or row["ts_end"]
    cf = conflicts(c, s, e, row["owner"], row["place"], exclude=a.id)
    if cf and not a.force:
        c.execute("rollback"); print("冲突：" + json.dumps(cf, ensure_ascii=False)); return 1
    c.execute("update events set ts_start=?,ts_end=?,updated=? where id=?", (s, e, now(), a.id)); c.execute("commit")
    print("MOVED #%d -> %s~%s" % (a.id, s, e)); return 0

def cmd_cancel(a):
    c = conn()
    n = c.execute("update events set status='cancelled',updated=? where id=? and status='active'", (now(), a.id)).rowcount
    c.commit(); print("CANCELLED #%d" % a.id if n else "无此事件 #%d" % a.id); return 0 if n else 1

def cmd_check(a):
    c = conn(); cf = conflicts(c, a.start, a.end, a.owner, a.place)
    if cf: print("冲突：" + json.dumps(cf, ensure_ascii=False)); return 1
    print("OK 无冲突"); return 0

def main():
    p = argparse.ArgumentParser(description="统一日历真源唯一写入口")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("title"); s.add_argument("--start", required=True); s.add_argument("--end", required=True)
    s.add_argument("--owner", default=""); s.add_argument("--agent", default=""); s.add_argument("--place", default="")
    s.add_argument("--kind", default="event"); s.add_argument("--source-ref", dest="source_ref", default=""); s.add_argument("--force", action="store_true"); s.set_defaults(func=cmd_add)
    s = sub.add_parser("list"); s.add_argument("--since"); s.add_argument("--until"); s.add_argument("--owner"); s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_list)
    s = sub.add_parser("move"); s.add_argument("id", type=int); s.add_argument("--start"); s.add_argument("--end"); s.add_argument("--force", action="store_true"); s.set_defaults(func=cmd_move)
    s = sub.add_parser("cancel"); s.add_argument("id", type=int); s.set_defaults(func=cmd_cancel)
    s = sub.add_parser("check"); s.add_argument("--start", required=True); s.add_argument("--end", required=True); s.add_argument("--owner", default=""); s.add_argument("--place", default=""); s.set_defaults(func=cmd_check)
    a = p.parse_args(); sys.exit(a.func(a))

if __name__ == "__main__":
    main()
