#!/usr/bin/env bash
# review-exchange.sh — 管家互审唯一交换口（包装 python，供 allowlist 调用）
exec /usr/bin/python3 /home/j/.openclaw/workspace/tools/review-exchange.py "$@"
