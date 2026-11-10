#!/usr/bin/env bash
# 人脸识别环境：venvs/face + cu13/cudnn 库路径（GPU 可用）
# 用法：source tools/face-env.sh && facepy tools/face-recognize.py ...
export FACE_VENV=/home/j/.openclaw/venvs/face
_NV=$FACE_VENV/lib/python3.14/site-packages/nvidia
export LD_LIBRARY_PATH=$_NV/cu13/lib:$_NV/cudnn/lib:${LD_LIBRARY_PATH:-}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-2}
facepy() { "$FACE_VENV/bin/python" "$@"; }
