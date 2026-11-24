#!/bin/bash
# music-id.sh — 听歌识曲（Shazam）v1.0
# 用法: bash tools/music-id.sh <视频/音频URL 或 本地文件>
# 输出: 单行 JSON {title, subtitle(艺人), Album, Label, Released, isrc, matches}
set -uo pipefail
V=/home/j/.openclaw/venvs/audioid
YT=/home/j/.local/bin/yt-dlp
FF=/home/j/.local/bin/ffmpeg
SRC="${1:-}"
if [ -z "$SRC" ]; then echo '{"error":"用法: music-id.sh <url|file>"}'; exit 2; fi
TMP=$(mktemp -d /tmp/music-id.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
if [ -f "$SRC" ]; then
  IN="$SRC"
else
  "$YT" -q --no-warnings -f 'ba/b' --no-playlist -o "$TMP/src.%(ext)s" "$SRC" >/dev/null 2>&1 || { echo '{"error":"下载失败"}'; exit 3; }
  IN=$(ls "$TMP"/src.* 2>/dev/null | head -1)
fi
[ -n "${IN:-}" ] || { echo '{"error":"无媒体文件"}'; exit 3; }
"$FF" -y -loglevel error -i "$IN" -vn -ac 1 -ar 16000 "$TMP/a.wav" || { echo '{"error":"抽音轨失败"}'; exit 4; }
"$V/bin/python" - "$TMP/a.wav" <<'PY' 2>/dev/null
import asyncio,json,sys
from shazamio import Shazam
async def main():
    out=await Shazam().recognize(sys.argv[1])
    t=out.get('track') or {}
    d={'title':t.get('title'),'subtitle':t.get('subtitle'),'isrc':t.get('isrc'),
       'matches':len(out.get('matches',[]) or [])}
    for s in t.get('sections') or []:
        for m in (s.get('metadata') or []):
            if m.get('title') in ('Album','Released','Genre','Label'):
                d[m['title']]=m.get('text')
    print(json.dumps(d,ensure_ascii=False))
asyncio.run(main())
PY
