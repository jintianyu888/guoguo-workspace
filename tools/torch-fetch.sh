#!/bin/sh
# torch-fetch.sh —— 用多连接分段拉 torch（ChatTTS 依赖，普通下载总断）→ 本地装入 py-chattts
cd /home/j/.openclaw/workspace || exit 1
LOG=state/torch-fetch.log
echo "[$(date "+%F %T")] 开始" >> $LOG
python3 - <<PY >> $LOG 2>&1
import json, urllib.request
d = json.load(urllib.request.urlopen("https://pypi.org/pypi/torch/json", timeout=25))
c = [f["url"] for f in d["urls"] if f["filename"].endswith(".whl") and "manylinux" in f["filename"] and "x86_64" in f["filename"] and "cp314" in f["filename"]]
if not c:
    c = [f["url"] for f in d["urls"] if f["filename"].endswith(".whl") and "manylinux" in f["filename"] and "x86_64" in f["filename"]]
open("state/torch-url.txt", "w").write(c[0])
print("URL", c[0][:90])
PY
U=$(head -n 1 state/torch-url.txt 2>/dev/null)
[ -n "$U" ] || { echo "取链接失败" >> $LOG; exit 1; }
N=$(basename "$U")
echo "[$(date "+%F %T")] 多连接下载 $N" >> $LOG
mkdir -p state/dl
timeout 5400 python3 tools/multi-dl.py "$U" "state/dl/$N" 16 >> $LOG 2>&1
echo "[$(date "+%F %T")] 下载完成 $(ls -lh state/dl/$N 2>/dev/null | awk "{print \$5}")" >> $LOG
tools/asr-venv/bin/pip install --target tools/py-chattts --no-deps "state/dl/$N" >> $LOG 2>&1
echo "[$(date "+%F %T")] torch 装入完成；继续装 ChatTTS 其余依赖" >> $LOG
timeout 1800 tools/asr-venv/bin/pip install --target tools/py-chattts -i https://pypi.tuna.tsinghua.edu.cn/simple ChatTTS >> $LOG 2>&1
echo "[$(date "+%F %T")] 结束" >> $LOG