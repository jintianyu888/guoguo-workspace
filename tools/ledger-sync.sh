#!/bin/bash
# ledger-sync.sh —— 每日把散落 JSONL 账本增量归一到三个 SQLite（幂等，可重跑）
set -u
W=/home/j/.openclaw/workspace
cd $W || exit 1
LOG=$W/state/work/ledger-sync.log
say(){ echo "[$(date "+%F %T")] $*" >> $LOG; }
say "开始"
python3 tools/ledger-merge.py state/backup/backup.db \
  state/backup-quiet/ledger.jsonl:state/backup-mirror-ledger.jsonl:state/backup-hash-ledger.jsonl:\
state/cloud-backup-ledger.jsonl:state/predanger-ledger.jsonl:state/restore-drill-ledger.jsonl:\
state/storage-cleanup-ledger.jsonl:state/backup/del-sample-hash.jsonl >> $LOG 2>&1
python3 tools/ledger-merge.py state/model-econ/model-econ.db \
  state/model-econ/quota-history.jsonl:state/model-econ/guard-decisions.jsonl:\
state/model-econ/balances.json:state/agent-usage-history.jsonl >> $LOG 2>&1
python3 tools/ledger-merge.py state/alerts/alerts.db \
  state/alerts/alerts.jsonl:state/work/maint-notices.jsonl:state/incidents/incidents.jsonl >> $LOG 2>&1
python3 tools/plan-db.py >> $LOG 2>&1
say "完成"
