#!/usr/bin/env bash
# 果果托管关机：停网关 -> 最终 checkpoint -> Windows 关机
set -x
sleep 5
date
systemctl --user stop openclaw-gateway
sleep 4
for db in /home/j/.openclaw/state/openclaw.sqlite /home/j/.openclaw/state/lcm.db /home/j/.openclaw/workspace/state/ledger/ledger.db; do
  [ -f "$db" ] && python3 -c "import sqlite3,sys;c=sqlite3.connect(sys.argv[1],timeout=10);c.execute('PRAGMA wal_checkpoint(TRUNCATE)');c.close();print('ckpt',sys.argv[1])" "$db"
done
sleep 2
/mnt/c/Windows/System32/shutdown.exe /s /t 20 /c "换机箱：果果托管关机"
echo "shutdown issued rc=$?"
sleep 60
