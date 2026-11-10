#!/bin/sh
# 整机资源采样：把当前 CPU/内存/磁盘写进当天日志（供日报算峰值）。
# 由定时任务每 10 分钟调用一次；不消耗任何 token。
STATUS_DIR="$HOME/.openclaw/workspace/status"
mkdir -p "$STATUS_DIR"
DAY=$(date +%F)
LOG="$STATUS_DIR/host-peak-$DAY.log"

# CPU 负载（1 分钟）
LOAD=$(cut -d' ' -f1 /proc/loadavg)
# 内存：used / total（GB，保留 1 位）
MEM=$(free -g | awk '/^Mem:/{printf "%s/%s", $3, $2}')
MEM_PCT=$(free | awk '/^Mem:/{printf "%.0f", $3/$2*100}')
# 交换
SWAP=$(free -g | awk '/^Swap:/{printf "%s/%s", $3, $2}')
# 磁盘（根分区，GB）
DISK=$(df -k / | awk 'NR==2{printf "%.0f/%.0f", $3/1048576, $2/1048576}')
DISK_PCT=$(df / | awk 'NR==2{gsub("%","",$5); print $5}')
# 最吃内存的进程
TOP=$(ps aux --sort=-%mem 2>/dev/null | sed -n '2p' | awk '{printf "%s(%.0f%%mem)", $11, $4}')

echo "$(date +%s) $(date +%H:%M) load=$LOAD mem=${MEM}GB(${MEM_PCT}%) swap=${SWAP}GB disk=${DISK}GB(${DISK_PCT}%) top=$TOP" >> "$LOG"

# 只保留最近 7 天
find "$STATUS_DIR" -name 'host-peak-*.log' -mtime +7 -delete 2>/dev/null
