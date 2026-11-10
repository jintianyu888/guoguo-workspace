#!/usr/bin/env bash
# fetch-fast.sh — 自动选最快线路下载（直连 vs Windows 代理），带断点续传与重试
# 用法: fetch-fast.sh <URL> <输出文件> [--sample MB]
set -uo pipefail
URL="${1:?用法: fetch-fast.sh <URL> <输出文件> [--sample MB]}"
OUT="${2:?缺少输出文件}"
SAMPLE="${4:-1}"
WINIP="$(ip route | awk '/^default/{print $3; exit}')"
PROXY=""
for p in 7890 7891 1080 10808 2080; do
  if timeout 1 bash -c "echo > /dev/tcp/$WINIP/$p" 2>/dev/null; then PROXY="http://$WINIP:$p"; break; fi
done

speed() { # $1=url $2=proxy-arg(可空)
  local r
  r=$(curl -sL $2 -o /dev/null --max-time 12 -r 0-1000000 -w '%{http_code} %{speed_download}' "$1" 2>/dev/null)
  local code=${r%% *} sp=${r##* }
  case "$code" in 200|206) echo "${sp%.*}" ;; *) echo 0 ;; esac
}

D=$(speed "$URL" "")
P=0; [ -n "$PROXY" ] && P=$(speed "$URL" "-x $PROXY")
echo "[fetch] 直连 ${D}B/s  代理 ${P}B/s  文件=$OUT" >&2

ARG=""
if [ "$P" -gt "$D" ] 2>/dev/null; then ARG="-x $PROXY"; echo "[fetch] 选代理" >&2; else echo "[fetch] 选直连" >&2; fi

for i in 1 2 3; do
  curl -L $ARG -C - --retry 3 --retry-delay 2 --max-time 3600 -o "$OUT" "$URL" 2>/dev/null
  rc=$?
  if [ $rc -eq 0 ] || [ $rc -eq 33 ]; then
    sz=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
    echo "[fetch] 完成 rc=$rc 大小=$sz" >&2
    exit 0
  fi
  echo "[fetch] 第 $i 次失败 rc=$rc，重试" >&2
  sleep 2
done
echo "[fetch] 放弃：三次都失败" >&2
exit 1
