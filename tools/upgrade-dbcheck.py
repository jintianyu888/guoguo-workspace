#!/usr/bin/env python3
"""升级前后读数：schema 版本 / 失败迁移数 / 真写探测。用法: upgrade-dbcheck.py schema|migfail|write"""
import sys, sqlite3
DB = "/home/j/.openclaw/state/openclaw.sqlite"
mode = sys.argv[1] if len(sys.argv) > 1 else "schema"
try:
    if mode == "schema":
        c = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
        print(c.execute("select schema_version from schema_meta where role=?", ("global",)).fetchone()[0])
    elif mode == "migfail":
        c = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
        print(c.execute("select count(*) from migration_runs where status != ?", ("completed",)).fetchone()[0])
    elif mode == "write":
        c = sqlite3.connect(DB, timeout=10)
        c.execute("create table if not exists __up_probe(x integer)")
        c.execute("insert into __up_probe values(1)")
        c.commit()
        c.execute("delete from __up_probe")
        c.commit()
        print("ok")
    else:
        sys.exit("未知模式 " + mode)
except Exception as e:
    sys.exit("ERR " + str(e))
