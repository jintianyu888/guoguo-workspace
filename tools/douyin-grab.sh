#!/usr/bin/env bash
# douyin-grab.sh — 抖音视频抓取（走已登录浏览器，免签名破解）
# 用法: douyin-grab.sh <抖音链接|视频ID> <输出.mp4>
# 原理: 在已登录的 Chrome 标签页里读 <video>.currentSrc（CDN 已签名直链），再 curl 下载。
# 依赖: openclaw CLI；浏览器 profile 需已登录抖音（默认 chrome，可用 BROWSER_PROFILE 覆盖）
# 退出码: 0成功 / 2用法 / 3打不开页面 / 4拿不到直链 / 5下载失败 / 6校验失败
set -uo pipefail

URL="$1"
OUT="$2"
if [ -z "$URL" ] || [ -z "$OUT" ]; then
  echo "用法: $0 <抖音链接|视频ID> <输出.mp4>" >&2
  exit 2
fi

PROFILE="${BROWSER_PROFILE:-chrome}"
MIN="${MIN_BYTES:-100000}"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36'

case "$URL" in
  *://*) LINK="$URL" ;;
  *) LINK="https://www.douyin.com/video/$URL" ;;
esac

TMPD="$(mktemp -d)"
cat > "$TMPD/js.txt" <<'JS'
async () => {
  const v = document.querySelector('video');
  if (!v) return '';
  v.muted = true;
  try { await v.play(); } catch (e) {}
  for (let i = 0; i < 12; i++) {
    if (v.currentSrc && /^https?:/.test(v.currentSrc)) return v.currentSrc;
    await new Promise(r => setTimeout(r, 1000));
  }
  return v.currentSrc || '';
}
JS

echo "[1/4] 打开页面: $LINK"
timeout 50 openclaw browser open --browser-profile "$PROFILE" "$LINK" --json > "$TMPD/open.json" 2>&1 || true
INFO="$(cat "$TMPD/open.json" 2>/dev/null)"
TID="$(printf '%s' "$INFO" | grep -oE '"targetId": *"[^"]+"' | head -1 | grep -oE '[A-Fa-f0-9]{16,}' | head -1)"
if [ -z "$TID" ]; then
  TID="$(timeout 30 openclaw browser tabs --browser-profile "$PROFILE" 2>/dev/null | awk '/douyin/{want=1;next} want&&/^[ ]*id:/{print $2; exit}')"
fi
if [ -z "$TID" ]; then
  echo "[!] 打不开页面（拿不到 targetId）" >&2
  printf '%s' "$INFO" | head -3 >&2
  rm -rf "$TMPD"
  exit 3
fi
echo "      tab=$TID"

cleanup() {
  openclaw browser close --browser-profile "$PROFILE" --target-id "$TID" >/dev/null 2>&1 || true
  rm -rf "$TMPD"
}
trap cleanup EXIT

echo "[2/4] 枚举清晰度档位（等播放器就绪，最多 12s）"
EV="openclaw browser evaluate --browser-profile $PROFILE --target-id $TID --fn"
# 先触发播放，让播放器把所有可用码流载入 performance
CAT_JS="$TMPD/js.txt"
SRC=""
BEST=0
for i in 0 1 2 3 4 5; do
  cat > "$TMPD/pick.js" <<JS
async () => {
  const v = document.querySelector('video');
  if (v) { v.muted = true; try { await v.play(); } catch (e) {} }
  await new Promise(r => setTimeout(r, 1500));
  const a = performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => n.indexOf('douyinvod') >= 0 && n.indexOf('media-video') >= 0);
  return a[$i] || '';
}
JS
  U="$($EV "$(cat "$TMPD/pick.js")" 2>/dev/null | tail -1 | sed 's/^"//' | sed 's/"$//')"
  [ "${#U}" -lt 50 ] && continue
  SZ="$(python3 - "$U" <<'PY'
import sys, urllib.request
u = sys.argv[1]
req = urllib.request.Request(u, method='HEAD', headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36','Referer':'https://www.douyin.com/'})
try:
    print(urllib.request.urlopen(req, timeout=20).headers.get('Content-Length') or 0)
except Exception:
    print(0)
PY
)"
  echo "      候选#$i size=$SZ"
  if [ "${SZ:-0}" -gt "$BEST" ] 2>/dev/null; then BEST="$SZ"; SRC="$U"; fi
done
if [ "${#SRC}" -lt 50 ]; then
  echo "[!] 拿不到视频直链（未登录 / 播放器未加载 / 链接失效）" >&2
  exit 4
fi
echo "      选中最大档 size=$BEST"

echo "[3/4] 下载 -> $OUT"
mkdir -p "$(dirname "$OUT")"
CODE="$(curl -sSL --max-time 300 -A "$UA" -H 'Referer: https://www.douyin.com/' -o "$OUT" "$SRC" -w '%{http_code}' 2>/dev/null)"
SZ="$(stat -c %s "$OUT" 2>/dev/null)"
if [ -z "$SZ" ]; then SZ=0; fi
echo "      http=$CODE bytes=$SZ"

echo "[4/4] 校验"
if [ "$CODE" != "200" ] || [ "$SZ" -lt "$MIN" ]; then
  echo "[!] 下载失败或不完整（http=$CODE bytes=$SZ < $MIN）" >&2
  exit 5
fi
if ! head -c 2000 "$OUT" | grep -qa 'ftyp'; then
  echo "[!] 文件不像 mp4（缺 ftyp）" >&2
  exit 6
fi
echo "OK $OUT ($SZ bytes)"
exit 0
