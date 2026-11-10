#!/bin/sh
# model-econ.sh — 模型经济唯一入口（主公令 2026-10-28 22:40：捏成一件事）
# 用法: model-econ.sh status|report|refresh|refresh-scrape|verify
set -u
cd /home/j/.openclaw/workspace || exit 1
case "${1:-report}" in
  status)  exec python3 tools/model-ops.py status ;;
  report)  exec python3 tools/model-ops.py report ;;
  refresh) exec python3 tools/model-ops.py refresh ;;
  refresh-scrape) exec python3 tools/model-ops.py refresh --scrape ;;
  verify)  exec python3 tools/model-ops.py verify ;;
  *) echo "用法: model-econ.sh status|report|refresh|refresh-scrape|verify"; exit 2 ;;
esac
