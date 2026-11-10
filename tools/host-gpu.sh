#!/bin/sh
# host-gpu.sh —— GPU 简要信息（WSL 内没有 nvidia-smi，走 Windows 侧 exe）
NVS=/mnt/c/Windows/System32/nvidia-smi.exe
[ -x "$NVS" ] || { echo "GPU：未找到 nvidia-smi.exe"; exit 0; }
name=$("$NVS" --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | tr -d "\r")
util=$("$NVS" --query-gpu=utilization.gpu --format=csv,noheader 2>/dev/null | head -1 | tr -d "\r")
mem=$("$NVS" --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1 | tr -d "\r")
[ -n "$name" ] || { echo "GPU：查询失败"; exit 0; }
printf "GPU：%s · 利用率 %s · 显存 %s\n" "$name" "$util" "$mem"