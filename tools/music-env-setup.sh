#!/bin/bash
# 给作曲管家建独立 venv 装 demucs/librosa（不动共享 tts312）
set -x
VENV=/home/j/.openclaw/venvs/demucs
PYBIN=$(command -v python3.12 || command -v python3)
"$PYBIN" -m venv "$VENV" || exit 1
"$VENV/bin/pip" install -q -U pip
"$VENV/bin/pip" install -q librosa demucs
echo "VENV-DONE rc=$?"
