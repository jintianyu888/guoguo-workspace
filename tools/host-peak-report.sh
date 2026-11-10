#!/bin/sh
# 整机资源日报：读当天采样日志，给出峰值/均值。
STATUS_DIR="${HOME:-/home/j}/.openclaw/workspace/status"
DAY=${1:-$(date +%F)}
LOG="$STATUS_DIR/host-peak-$DAY.log"

if [ ! -s "$LOG" ]; then
  echo "📊 整机资源日报（$DAY）：今天还没有采样数据"
  exit 0
fi

echo "📊 整机资源日报（$DAY）· 采样 $(wc -l < "$LOG") 次"
echo

# CPU 负载峰值
awk -F'load=' '{split($2,a," "); if(a[1]+0>m) m=a[1]+0} END{printf "  CPU 负载峰值：%.2f（16 线程，>8 才算忙）\n", m}' "$LOG"

# 内存峰值
awk -F'mem=' '{split($2,a,"GB"); gsub(/[0-9]+\//,"",a[1]); }' "$LOG" >/dev/null 2>&1
awk '{
  if (match($0, /mem=[0-9]+\/([0-9]+)GB\(([0-9]+)%\)/, m)) { if (m[2]+0>max) max=m[2]+0; if (m[1]+0>tot) tot=m[1]+0 }
} END{printf "  内存峰值：%d%% 占用（总 %dGB）\n", max, tot}' "$LOG"

# 磁盘
tail -1 "$LOG" | awk '{for(i=1;i<=NF;i++) if($i ~ /^disk=/) d=$i} END{print "  磁盘当前："d}'

# 最吃资源的进程（取最后一次采样）
tail -1 "$LOG" | awk -F'top=' '{print "  最占内存进程："$2}'

echo
echo "  （采样间隔 10 分钟；要更细可调）"
