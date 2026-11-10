#!/bin/sh
# footer-tasks.sh —— 任务区唯一来源（2026-10-18 主公令）
# 旧版读 LEDGER 的「## ⏸ / ## 🟢」段落，容易随改动丢失；现统一走 state/tasks/tasks.json
exec python3 /home/j/.openclaw/workspace/tools/tasks-footer.py

