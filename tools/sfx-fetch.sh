#!/bin/bash
# sfx-fetch.sh — 受控音效获取（仅 Mixkit / Pixabay 域名），输出只写 music 工作区
# 用法：sfx-fetch.sh --id 951 [--name 09-short-pop.mp3] [--len 0.90] [--peak -1.5] [--dry]
set -euo pipefail
W=/home/j/.openclaw/workspace
mkdir -p "$W/state/tmp"
FF=/home/j/.local/bin/ffmpeg
OUT_DIR=/home/j/openclaw-workspaces/music/ringtones
ALLOW_HOSTS="assets.mixkit.co pixabay.com cdn.pixabay.com"

ID=""; URL=""; NAME=""; LEN="0.90"; PEAK="-1.5"; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --id) ID="$2"; shift 2;;
    --url) URL="$2"; shift 2;;
    --name) NAME="$2"; shift 2;;
    --len) LEN="$2"; shift 2;;
    --peak) PEAK="$2"; shift 2;;
    --dry) DRY=1; shift;;
    *) echo "未知参数: $1" >&2; exit 2;;
  esac
done

if [ -n "$ID" ]; then
  case "$ID" in (*[!0-9]*) echo "ID 必须是数字" >&2; exit 2;; esac
  URL="https://assets.mixkit.co/active_storage/sfx/$ID/$ID-preview.mp3"
fi
[ -n "$URL" ] || { echo "用法: sfx-fetch.sh --id <mixkit数字ID> | --url <https://允许域名/...>" >&2; exit 2; }

HOST=$(printf '%s' "$URL" | sed -E 's#^https?://([^/]+).*#\1#')
OK=0
for h in $ALLOW_HOSTS; do [ "$HOST" = "$h" ] && OK=1; done
[ "$OK" = 1 ] || { echo "拒绝：域名 $HOST 不在白名单（$ALLOW_HOSTS）" >&2; exit 3; }

[ -n "$NAME" ] || NAME="sfx-$(date +%s).mp3"
case "$NAME" in (*/*|*..*) echo "输出名不允许包含路径" >&2; exit 2;; esac
case "$NAME" in (*.mp3) ;; (*) echo "输出名必须以 .mp3 结尾" >&2; exit 2;; esac

TMP=$(mktemp -d "$W/state/tmp/sfx-XXXXXX")
trap 'rm -rf "$TMP"' EXIT

echo "获取: $URL"
curl -sS --max-time 30 -A "Mozilla/5.0" -o "$TMP/src.mp3" "$URL"
SRC_DUR=$($FF -hide_banner -i "$TMP/src.mp3" 2>&1 | sed -n 's/.*Duration: \([0-9:.]*\).*/\1/p' | head -1 || true)
echo "素材原始时长: $SRC_DUR"

/usr/bin/python3 - "$TMP/src.mp3" "$TMP/cut.wav" "$LEN" <<'PY'
import sys, subprocess, wave, array
FF="/home/j/.local/bin/ffmpeg"
src, dst, ln = sys.argv[1], sys.argv[2], float(sys.argv[3])
subprocess.run([FF,"-hide_banner","-loglevel","error","-y","-i",src,"-ar","44100","-ac","1","-c:a","pcm_s16le",dst+"_full.wav"],check=True)
with wave.open(dst+"_full.wav","rb") as f:
    sr=f.getframerate(); a=array.array("h"); a.frombytes(f.readframes(f.getnframes()))
pk=max(max(a),-min(a)) or 1
first=next(k for k,v in enumerate(a) if abs(v)>pk*0.15)
start=max(0, first-int(0.015*sr))
want=min(int(ln*sr), len(a)-start)
seg=array.array("h", a[start:start+want])
fo=min(int(0.02*sr), len(seg))
for i in range(fo): seg[len(seg)-fo+i]=int(seg[len(seg)-fo+i]*(1-i/fo))
with wave.open(dst,"wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(seg.tobytes())
print("切出: %.2fs"%(len(seg)/sr))
PY

MV=$($FF -hide_banner -i "$TMP/cut.wav" -af volumedetect -f null - 2>&1 | sed -n 's/.*max_volume: *\(-*[0-9.]*\) dB.*/\1/p' | head -1)
GAIN=$(awk -v mv="$MV" -v t="$PEAK" 'BEGIN{printf "%.2f", t-mv}')
echo "峰值 $MV dBFS -> 增益 $GAIN dB（目标 $PEAK dBFS）"

if [ "$DRY" = 1 ]; then
  $FF -hide_banner -y -i "$TMP/cut.wav" -af "volume=$GAIN""dB" -ar 44100 -ac 1 -c:a libmp3lame -b:a 128k "$TMP/out.mp3"
  echo "[dry] 成品 $TMP/out.mp3（$(stat -c%s "$TMP/out.mp3") B），未写入 $OUT_DIR"
  exit 0
fi

mkdir -p "$OUT_DIR"
$FF -hide_banner -loglevel error -y -i "$TMP/cut.wav" -af "volume=$GAIN""dB" -ar 44100 -ac 1 -c:a libmp3lame -b:a 128k "$OUT_DIR/$NAME"
FINAL_DUR=$($FF -hide_banner -i "$OUT_DIR/$NAME" 2>&1 | sed -n 's/.*Duration: \([0-9:.]*\).*/\1/p' | head -1 || true)
FPK=$($FF -hide_banner -i "$OUT_DIR/$NAME" -af volumedetect -f null - 2>&1 | sed -n 's/.*max_volume: *\(-*[0-9.]*\) dB.*/\1/p' | head -1)
echo "OK $OUT_DIR/$NAME | 成品 $FINAL_DUR | 峰值 $FPK dBFS | $(stat -c%s "$OUT_DIR/$NAME") B"
