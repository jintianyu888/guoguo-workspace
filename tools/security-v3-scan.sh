#!/bin/bash
# 网关托管的 v3 NVR 扫描（1401）——脚本自带日志到 state/work/nvr-scan-v3.log
PY=/home/j/.openclaw/venvs/face/bin/python
exec "$PY" /home/j/openclaw-workspaces/security/tools/nvr-scan-v3.py --channels 1401 --date 2026-10-13 --hours 7-23 --verbose
