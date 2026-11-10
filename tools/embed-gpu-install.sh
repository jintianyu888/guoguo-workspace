#!/bin/sh
# embed-gpu-install.sh —— 给 embed-venv 装 onnxruntime-gpu（后台，走镜像），装完自证
L=/home/j/.openclaw/workspace/state/embed-gpu.log
echo "[$(date '+%F %T')] 开始" >> $L
P=/home/j/.openclaw/workspace/tools/embed-venv/bin/pip
D=$(ls -d /home/j/.openclaw/workspace/tools/embed-venv/lib/python*/site-packages | head -n 1)
timeout 1200 $P install --upgrade -i https://pypi.tuna.tsinghua.edu.cn/simple onnxruntime-gpu >> $L 2>&1
echo "[$(date '+%F %T')] 装完 rc=$?" >> $L
$D/../../bin/python -c "import onnxruntime as o;print('providers',o.get_available_providers())" >> $L 2>&1
echo "[$(date '+%F %T')] 自证结束" >> $L