#!/usr/bin/env bash
# r31: 双顾问必须用各厂顶级模型（千问 -max / 智谱不带 -flash）
WS=/home/j/.openclaw/workspace
Q=$(grep -oE 'qianwen-token-plan/[a-z0-9.\-]+' "$WS/tools/advice.sh" | head -1)
G=$(grep -oE 'zai/[a-z0-9.\-]+' "$WS/tools/advice.sh" | head -1)
fail=0
case "$Q" in *-max) ;; *) echo "FAIL 千问顾问不是顶级模型：$Q"; fail=1;; esac
case "$G" in *flash*) echo "FAIL 智谱顾问用了 flash：$G"; fail=1;; zai/glm-*) ;; *) echo "FAIL 智谱顾问未配置：$G"; fail=1;; esac
[ -f "$WS/state/model-econ/refresh.json" ] || { echo "FAIL 缺模型刷新快照"; fail=1; }
[ $fail -eq 0 ] && echo "PASS 顾问模型=$Q / $G；刷新快照在 state/model-econ/refresh.json"
exit $fail
