import sqlite3, datetime, sys
DB="/home/j/.openclaw/workspace/state/tasks/tasks.db"
APPLY = "--apply" in sys.argv
c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
cut=(datetime.date.today()-datetime.timedelta(days=30)).isoformat()
recent21=(datetime.date.today()-datetime.timedelta(days=21)).isoformat()
rows=[dict(r) for r in c.execute("select * from tasks where status in ('pending','open','in_progress')")]
def upd(t): return (t.get("updated") or "2000-01-01")[:10]
park=[t for t in rows if (t.get("who") or "agent")!="owner" and not t.get("blocked") and upd(t) < cut]
stale=[t for t in rows if (t.get("who") or "agent")!="owner" and not t.get("blocked") and cut <= upd(t) < recent21]
print("自动封存候选 %d 项（>30天无进展）:" % len(park))
for t in park: print("  #%s %s" % (t["no"], (t["title"] or "")[:46]))
print("待裁决 %d 项（21-30天）:" % len(stale))
for t in stale: print("  #%s %s" % (t["no"], (t["title"] or "")[:46]))
if APPLY:
    now=datetime.datetime.now().isoformat(timespec="seconds")
    for t in park:
        c.execute("update tasks set status='paused', updated=? where no=?", (now, t["no"]))
        c.execute("insert into events(ts,no,field,old,new,actor,reason) values(?,?,?,?,?,?,?)", (now, t["no"], "status", t["status"], "paused", "agent", "自动封存：30天无进展"))
    c.commit(); print("已封存", len(park), "项")
else: print("[dry-run]")