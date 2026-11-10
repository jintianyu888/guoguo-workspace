#!/bin/bash
# hw-temp.sh — 只读硬件温度采集（无需安装任何软件）
NVS=/usr/lib/wsl/lib/nvidia-smi
if [ -x "$NVS" ]; then
  out=$(timeout 6 "$NVS" --query-gpu=temperature.gpu,fan.speed,utilization.gpu,memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
  if [ -n "$out" ]; then
    t=$(echo "$out" | cut -d, -f1 | tr -d ' ')
    f=$(echo "$out" | cut -d, -f2 | tr -d ' ')
    u=$(echo "$out" | cut -d, -f3 | tr -d ' ')
    m=$(echo "$out" | cut -d, -f4 | tr -d ' ')
    echo "GPU $t C / 风扇 $f % / 负载 $u % / 显存 $m MiB"
  fi
fi
if [ -r /sys/class/thermal/thermal_zone0/temp ]; then
  echo "CPU $(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp) C"
else
  echo "CPU 温度 不可得（WSL 无 ACPI 温区）"
fi
