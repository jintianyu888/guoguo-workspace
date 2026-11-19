#!/bin/bash
# 回滚：把 asr-venv / embed-venv 恢复到 2026-11-05 08:10 的版本快照
set -uo pipefail
W=/home/j/.openclaw/workspace
RB=$W/state/rollback/pkg-20261105
IDX="https://pypi.tuna.tsinghua.edu.cn/simple"
for V in asr-venv embed-venv; do
  P=$W/tools/$V/bin/python3
  echo "=== rollback $V ==="
  "$P" -m pip install --index-url "$IDX" --no-input -r "$RB/$V-freeze.txt" 2>&1 | tail -5
done
echo "=== verify ==="
$W/tools/asr-venv/bin/python3 -c 'import faster_whisper, av, huggingface_hub; print("asr imports ok")'
$W/tools/embed-venv/bin/python3 -c 'import fastembed; print("embed imports ok")'
