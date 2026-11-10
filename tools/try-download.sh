#!/bin/sh
# try-download.sh —— 试"多连接分段下载"取 CUDA 大包（镜像优先，官方兜底）
cd /home/j/.openclaw/workspace || exit 1
echo "== 取 wheel 直链 =="
python3 tools/get-wheel-url.py 2>&1 | tail -n 2
U=$(head -n 1 state/wheel-url.txt 2>/dev/null)
[ -n "$U" ] || { echo "取链接失败"; exit 1; }
echo "URL=${U}"
echo "== 多连接下载（8 段并行，限 120 秒） =="
S=$(date +%s)
timeout 120 python3 tools/multi-dl.py "$U" /home/j/.openclaw/workspace/state/tmp/cublas.whl 8 2>&1 | tail -n 4
E=$(date +%s)
echo "墙钟=$((E-S))s"
ls -lh /home/j/.openclaw/workspace/state/tmp/cublas.whl 2>/dev/null | awk "{print \"已下:\", \$5}"
du -ch /home/j/.openclaw/workspace/state/tmp/cublas.whl.part* 2>/dev/null | tail -n 1