#!/bin/sh
# tts.sh —— 本地语音合成（Piper，离线、零 token）
# 用法: tools/tts.sh "要读的文字" [输出.wav|.ogg]
set -e
W=/home/j/.openclaw/workspace
TXT="${1:?用法: tts.sh \"文字\" [out.wav]}"; OUT="${2:-/home/j/.openclaw/workspace/state/tmp/tts-out.ogg}"
# 2026-10-05：默认走本地 GPU（Kokoro-82M）；不可用时回退 Piper。TTS_ENGINE=piper 可强制旧引擎。
if [ "${TTS_ENGINE:-gpu}" = "gpu" ] && [ -x /home/j/.openclaw/venvs/tts312/bin/python ]; then
  exec sh "$W/tools/tts-gpu.sh" "$TXT" "$OUT" "${TTS_VOICE:-zf_xiaoxiao}"
fi
M=$W/tools/models/piper/zh_CN-huayan-medium.onnx
[ -f "$M" ] || { echo "缺音色模型: $M"; exit 1; }
WAV=$(mktemp /home/j/.openclaw/workspace/state/tmp/tts-XXXX.wav)
PYTHONPATH="$W/tools/py-tts" printf %s "$TXT" | PYTHONPATH="$W/tools/py-tts" "$W/tools/asr-venv/bin/python" -m piper -m "$M" -f "$WAV" --length-scale 1.15 --sentence-silence 0.35 >/dev/null 2>&1
case "$OUT" in
  *.ogg) PYTHONPATH="$W/tools/py-tts" "$W/tools/asr-venv/bin/python" - "$WAV" "$OUT" <<PY
import av, sys
wav, out = sys.argv[1], sys.argv[2]
i = av.open(wav); o = av.open(out, mode="w")
s = o.add_stream("libopus", rate=24000)
for fr in i.decode(audio=0):
    fr.pts = None
    for p in s.encode(fr): o.mux(p)
for p in s.encode(): o.mux(p)
o.close(); i.close(); print("写成:", out)
PY
  ;;
  *) cp "$WAV" "$OUT"; echo "写成: $OUT";;
esac
ls -lh "$OUT" 2>/dev/null | awk "{print \"体积:\", \$5}"