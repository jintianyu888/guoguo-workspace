#!/bin/sh
# probe.sh —— 一步到位：查 Windows 工具 + 启动 dl-fast + 报告进度
cd /home/j/.openclaw/workspace || exit 1
echo '## Windows 侧工具'
command -v powershell.exe >/dev/null 2>&1 && echo 'powershell.exe OK' || echo 'powershell.exe NO'
command -v curl.exe >/dev/null 2>&1 && echo 'curl.exe OK' || echo 'curl.exe NO'
echo '## 启动多连接下载'
U='https://pypi.tuna.tsinghua.edu.cn/packages/13/d3/e20e514bf32e770d1aa324bfeac1ba31b3893c934b14ad2fb57437b857c6/nvidia_cudnn_cu12-9.9.0.52-py3-none-manylinux_2_27_x86_64.whl'
pkill -f 'dl-fast' 2>/dev/null
setsid nohup sh tools/dl-fast.sh "$U" state/dl/nvidia_cudnn_cu12-9.9.0.52.whl 8 > state/dl-fast.log 2>&1 < /dev/null &
sleep 40
echo '## 40 秒后'
tail -n 4 state/dl-fast.log 2>/dev/null
echo "parts=$(ls state/dl/nvidia_cudnn_cu12-9.9.0.52.whl.part* 2>/dev/null | wc -l) curl=$(pgrep -cf curl)"
du -sh state/dl | cut -f1