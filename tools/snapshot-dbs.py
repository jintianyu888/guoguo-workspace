import sqlite3,sys,os
bk=sys.argv[1]
srcs=["/home/j/.openclaw/state/openclaw.sqlite","/home/j/.openclaw/lcm.db","/home/j/.openclaw/workspace/state/tasks/tasks.db"]
for src in srcs:
    if not os.path.exists(src):
        print("  skip",src); continue
    dst=os.path.join(bk,os.path.basename(src))
    c=sqlite3.connect("file:"+src+"?mode=ro",uri=True)
    d=sqlite3.connect(dst); c.backup(d); d.close(); c.close()
    print("  %-18s %6.1fMB"%(os.path.basename(src),os.path.getsize(dst)/1048576))
