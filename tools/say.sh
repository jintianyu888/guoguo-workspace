#!/bin/bash
# say.sh — 一句话出语音（本地 F5-TTS 克隆音色 / 微软晓伊可选）
# 用法:
#   say.sh "要念的文字"                  # 默认女声 A（本地 F5 克隆音色）
#   say.sh "文字" --voice zhu            # 主公音色（本地 F5）
#   say.sh "文字" --voice edge           # 微软晓伊（云端中文，需联网）
#   say.sh "文字" --voice edge-en        # 微软 Emma（英文原生，中英混读自然）★英语老师用
#   say.sh "文字" --voice edge-en-m      # 微软 Andrew（英文男声）
#   say.sh "文字" --voice edge-zh        # 微软晓晓（中文女声）
#   say.sh "文字" --voice cloud          # 按语种自动选云端音色，失败自动回落本地 F5
#   say.sh "文字" --out /tmp/x.opus      # 指定输出
#   say.sh "文字" --format wav           # 输出 wav
# 说明: 本地引擎零 token、离线；参考样本在 /home/j/.config/guoguo/voice-ref (600)
set -uo pipefail

TEXT=""; VOICE="f5a"; OUT=""; FMT="opus"; INSTRUCT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --voice) VOICE="$2"; shift 2;;
    --out)   OUT="$2"; shift 2;;
    --format) FMT="$2"; shift 2;;
    --instruct) INSTRUCT="$2"; shift 2;;
    -h|--help) sed -n "2,12p" "$0"; exit 0;;
    *) TEXT="$TEXT${TEXT:+ }$1"; shift;;
  esac
done
[ -z "$TEXT" ] && { echo '用法: say.sh "文字" [--voice f5a|zhu|edge|edge-en|edge-en-m|edge-zh|cloud|cosy] [--out 文件] [--format opus|wav]' >&2; exit 2; }

D=/home/j/.config/guoguo/voice-ref
V=/home/j/.openclaw/venvs/tts-neural
E=${E:-/home/j/.openclaw/venvs/tts-edge/bin/python}  # 可覆盖，便于测试云端失败回落
FF=/home/j/.local/bin/ffmpeg
mkdir -p "$D/samples"
TS=$(date +%H%M%S)
[ -z "$OUT" ] && OUT="$D/samples/say-$TS.$FMT"

case "$VOICE" in
  f5a)
    REF="$D/female-ref.wav"; REFT='今天天气不错，我们把这一段话当成参考样本，语速放慢一点，声音清楚一点。';;
  zhu)
    REF="$D/zhuyin-ref.wav"; REFT='你就看按八G显卡可以运行的一个好的模型是什么样的，你来一个，就是让它更好';;
  cosy)
    V2=/home/j/.openclaw/venvs/tts-cosy/bin/python
    TMP=$(mktemp -d /tmp/sayc.XXXXXX)
    "$V2" /home/j/.openclaw/workspace/tools/cosy_say.py "$TEXT" --out "$TMP/o.wav" --instruct "$INSTRUCT" >"$TMP/log" 2>&1
    [ -s "$TMP/o.wav" ] || { echo "cosy 合成失败: $TMP/log" >&2; exit 6; }
    if [ "$FMT" = "opus" ]; then "$FF" -y -loglevel error -i "$TMP/o.wav" -c:a libopus -b:a 48k -ac 1 "$OUT"; else cp "$TMP/o.wav" "$OUT"; fi
    rm -rf "$TMP"; chmod 600 "$OUT" 2>/dev/null; echo "$OUT"; exit 0;;
  edge-en|edge-en-m|edge-zh|cloud)
    case "$VOICE" in
      edge-en) EV=en-US-EmmaMultilingualNeural; ER=-2% ;;
      edge-en-m) EV=en-US-AndrewMultilingualNeural; ER=-2% ;;
      edge-zh) EV=zh-CN-XiaoxiaoNeural; ER=-4% ;;
      cloud)
        CJKN=$(printf %s "$TEXT" | grep -o -P '[\x{4e00}-\x{9fff}]' | wc -l)
        TLEN=$(printf %s "$TEXT" | wc -c)
        if [ "$TLEN" -gt 0 ] && [ $((CJKN*3)) -ge "$TLEN" ]; then EV=zh-CN-XiaoxiaoNeural; else EV=en-US-EmmaMultilingualNeural; fi
        ER=-3% ;;
    esac
    if "$E" -m edge_tts --voice "$EV" --rate="$ER" --text "$TEXT" --write-media "$OUT.mp3" >/dev/null 2>&1 && [ -s "$OUT.mp3" ]; then
      if [ "$FMT" = "opus" ]; then "$FF" -y -loglevel error -i "$OUT.mp3" -c:a libopus -b:a 48k -ac 1 "$OUT" && rm -f "$OUT.mp3"; else mv "$OUT.mp3" "$OUT"; fi
      chmod 600 "$OUT" 2>/dev/null; echo "$OUT"; exit 0
    fi
    rm -f "$OUT.mp3"
    echo "云端合成失败($EV)，回落本地 F5" >&2
    exec bash /home/j/.openclaw/workspace/tools/say.sh "$TEXT" --voice f5a --out "$OUT" --format "$FMT" ;;
  edge)
    "$E" -m edge_tts --voice zh-CN-XiaoyiNeural --rate=-4% --text "$TEXT" --write-media "$OUT.mp3" >/dev/null 2>&1 || { echo "edge-tts 失败" >&2; exit 3; }
    if [ "$FMT" = "opus" ]; then "$FF" -y -loglevel error -i "$OUT.mp3" -c:a libopus -b:a 48k -ac 1 "$OUT" && rm -f "$OUT.mp3"; else mv "$OUT.mp3" "$OUT"; fi
    chmod 600 "$OUT" 2>/dev/null; echo "$OUT"; exit 0;;
  *) echo "未知音色: $VOICE" >&2; exit 2;;
esac

TMP=$(mktemp -d /tmp/say.XXXXXX)
"$V/bin/python" /home/j/.openclaw/workspace/tools/f5_run.py \
  --model F5TTS_v1_Base --ref_audio "$REF" --ref_text "$REFT" \
  --gen_text "$TEXT" --output_dir "$TMP" --device cuda >"$TMP/log" 2>&1
RC=$?
WAV=$(ls "$TMP"/*.wav 2>/dev/null | head -1)
if [ $RC -ne 0 ] || [ -z "$WAV" ]; then echo "合成失败，日志: $TMP/log" >&2; exit 4; fi
if [ "$FMT" = "opus" ]; then
  "$FF" -y -loglevel error -i "$WAV" -c:a libopus -b:a 48k -ac 1 "$OUT" || exit 5
else
  cp "$WAV" "$OUT"
fi
rm -rf "$TMP"
chmod 600 "$OUT" 2>/dev/null
echo "$OUT"
