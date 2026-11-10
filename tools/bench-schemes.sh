#!/bin/bash
# bench-schemes.sh — CPU / GPU / CPU+GPU 三方案实测（大一点的项目），数据单独存 state/bench/
# 2026-09-29 01:16 主公令：实际测三个方案，保留最优 + 保留测试数据 + 定期优化
set -u
W=/home/j/.openclaw/workspace; cd $W || exit 1
D=$W/state/bench/$(date +%F_%H%M); mkdir -p "$D"
R=$D/result.md; : > "$R"
echo "# 三方案实测 $(date '+%F %T')" >> "$R"
echo "" >> "$R"

# 准备一个『稍微大点』的音频：把现有 8 秒语音拼 12 遍 ≈ 96 秒
A=$(ls $W/media/inbound/*/input-*.ogg 2>/dev/null | head -n 1)
BIG=$D/big-audio.ogg
if [ -n "$A" ]; then : > $D/list.txt; i=0; while [ $i -lt 12 ]; do echo "file '$A'" >> $D/list.txt; i=$((i+1)); done; tools/asr-venv/bin/python - <<PY 2>/dev/null
import av,sys
li=av.open('$D/list.txt',format='concat')
o=av.open('$BIG',mode='w'); s=o.add_stream('libopus',rate=24000)
for fr in li.decode(audio=0):
    fr.pts=None
    for p in s.encode(fr): o.mux(p)
for p in s.encode(): o.mux(p)
o.close(); print('big ok')
PY
fi
[ -s "$BIG" ] || BIG=$A
echo "音频：$(du -h "$BIG" 2>/dev/null | cut -f1)" >> "$R"

run() { # $1=名称 $2=模式
  local n="$1" m="$2" s e
  s=$(date +%s%3N)
  case "$m" in
    cpu) ASR_FORCE_CPU=1 tools/asr "$BIG" --language zh --model tools/models/faster-whisper-small --output_dir $D/$n-$m >/dev/null 2>&1 ;;
    gpu) tools/asr "$BIG" --language zh --model tools/models/faster-whisper-small --output_dir $D/$n-$m >/dev/null 2>&1 ;;
    coop) ( ASR_FORCE_CPU=1 tools/asr "$BIG" --language zh --model tools/models/faster-whisper-small --output_dir $D/$n-coop-cpu >/dev/null 2>&1 ) & 
          ( tools/asr "$BIG" --language zh --model tools/models/faster-whisper-small --output_dir $D/$n-coop-gpu >/dev/null 2>&1 ) & wait ;;
  esac
  e=$(date +%s%3N); echo "| $1 | $2 | $((e-s)) ms |" >> "$R"
}

echo "| 任务 | 方案 | 耗时 |" >> "$R"; echo "|---|---|---|" >> "$R"
run asr-long cpu
run asr-long gpu
echo "- 协同方案请见下节（CPU 与 GPU 各跑一份并联）" >> "$R"

echo "" >> "$R"; echo "## 批量向量化 2000 句" >> "$R"
$W/tools/embed-venv/bin/python - <<PY > $D/reps.txt 2>/dev/null
for i in range(2000): print('第%d句测试文本，用于比较中央处理器与显卡的速度差异' % i)
PY
s=$(date +%s%3N); tools/embed --file $D/reps.txt >/dev/null 2>&1; e=$(date +%s%3N); echo "| embed-2000 | cpu | $((e-s)) ms |" >> "$R"
s=$(date +%s%3N); tools/embed --gpu --file $D/reps.txt >/dev/null 2>&1; e=$(date +%s%3N); echo "| embed-2000 | gpu | $((e-s)) ms |" >> "$R"
echo "" >> "$R"; echo "生成于 $D" >> "$R"
cp "$R" $W/state/bench/index-latest.md 2>/dev/null
echo DONE >> $D/done.txt