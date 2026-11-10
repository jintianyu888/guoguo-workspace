#!/usr/bin/env bash
# upgrade-b.sh — 升级 B 机(MyPC-Node) 的 OpenClaw（2026-11-07 主公令：A 升级成功后同步升级 B）
# 用法: upgrade-b.sh [目标版本]   不传则取 npm 最新版
set -u
TGT="${1:-}"
NODE="${NODE_NAME:-MyPC-Node}"
EXE=/home/j/.npm-global/bin/openclaw
say(){ echo "$(date '+%F %T') $*"; }
params(){ python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$1"; }
inv(){ timeout 1200 "$EXE" nodes invoke --node "$NODE" --invoke-timeout 900000 --timeout 900000 --command system.run --params "$(params "$1")" 2>&1; }
ver(){ inv "openclaw --version" | grep -oE "2026\.[0-9]+\.[0-9]+" | tail -1; }

[ -x "$EXE" ] || { say "找不到 $EXE"; exit 64; }
BEFORE=$(ver); say "B 机当前版本：${BEFORE:-未知}"
if [ -z "$TGT" ]; then TGT=$(timeout 90 npm view openclaw version 2>/dev/null | tail -1); fi
[ -z "$TGT" ] && { say "取不到目标版本，放弃"; exit 65; }
say "目标版本：$TGT"
if [ "$BEFORE" = "$TGT" ]; then say "B 机已是 $TGT，跳过"; exit 0; fi
say "步骤 1/4：npm 全局安装（在 B 机上跑）"
inv "npm i -g openclaw@$TGT --no-audit --no-fund" | tail -3
say "步骤 2/4：重启 B 机 OpenClaw Node 计划任务"
inv 'schtasks /end /tn "OpenClaw Node"' | tail -2
sleep 3
inv 'schtasks /run /tn "OpenClaw Node"' | tail -2
say "步骤 3/4：等待回连并校验版本（最多 10 分钟）"
OK=0
for i in $(seq 1 40); do
  sleep 15
  AFTER=$(ver 2>/dev/null)
  if [ "$AFTER" = "$TGT" ]; then OK=1; say "B 机已到 $TGT（第 $i 次探测）"; break; fi
  say "  第 $i 次：${AFTER:-未连上}"
done
say "步骤 4/4：节点连接状态"
"$EXE" nodes list 2>/dev/null | grep -A2 -i "$NODE" | head -6
if [ "$OK" = "1" ]; then say "B 机升级成功：$BEFORE → $TGT"; exit 0; fi
say "B 机升级未确认（当前 ${AFTER:-未知}），需人工检查 npm 全局目录与计划任务"
exit 1