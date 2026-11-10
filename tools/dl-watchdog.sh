#!/bin/sh
# dl-watchdog.sh v2 —— 下载重试（低频、限次）：失败 3 次后改为每 6 小时一次，不再打扰
# 2026-09-29 00:1x 主公指出「总是停在同一个数」：分片器对大包一轮 0/16 段 → 改为低频重试
W=/home/j/.openclaw/workspace
LOG=$W/state/dl-watchdog.log
CNT=$W/state/.dl-wd-count
n=$(cat $CNT 2>/dev/null || echo 0)
if [ -f "$W/state/dl/nvidia_cudnn_cu12-9.9.0.52.whl" ] && [ -f "$W/state/dl/torch-2.14.0-cp314-cp314-manylinux_2_28_x86_64.whl" ]; then
  echo "[$(date '+%F %T')] 两个包都在，收工" >> $LOG; exit 0
fi
case "$n" in
  0|1|2) ;;
  *) [ -f "$W/state/.dl-wd-demoted" ] || { echo "[$(date '+%F %T')] 已重试 $n 次仍未成 → 放弃重试（包非必需）" >> $LOG; touch "$W/state/.dl-wd-demoted"; }; exit 0 ;;
esac
echo "$((n+1))" > $CNT
echo "[$(date '+%F %T')] 第 $((n+1)) 次重试（wget 断点续传）" >> $LOG
pkill -f multi-dl 2>/dev/null
U1="https://pypi.tuna.tsinghua.edu.cn/packages/13/d3/e20e514bf32e770d1aa324bfeac1ba31b3893c934b14ad2fb57437b857c6/nvidia_cudnn_cu12-9.9.0.52-py3-none-manylinux_2_27_x86_64.whl"
setsid nohup sh -c "cd $W/state/dl && wget -4 -c -q --timeout=45 --tries=3 -O nvidia_cudnn_cu12-9.9.0.52.whl '$U1' >> $W/state/wget-dl.log 2>&1" >/dev/null 2>&1 < /dev/null &
echo "[$(date '+%F %T')] 已启动 pid=$!" >> $LOG