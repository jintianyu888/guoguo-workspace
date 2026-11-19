#!/usr/bin/env bash
set -euo pipefail
DIR="/home/j/.openclaw/workspace/tools"
exec python3 "$DIR/label-print.py" "$@"
