#!/bin/sh
# footer-dl.sh —— 页脚下载进度（零 token）：已下/总大小/百分比/速度/预计剩余
W=/home/j/.openclaw/workspace
DL=$W/state/dl
found=0
for L in cudnn-fetch torch-fetch cuda-fetch; do
  LOG=$W/state/$L.log
  [ -f "$LOG" ] || continue
  # 取最近一次 "大小 X MB" 与目标名
  TOTMB=$(grep -oE "大小 [0-9.]+ MB" "$LOG" 2>/dev/null | tail -n 1 | grep -oE "[0-9.]+")
  TGT=$(grep -oE "下载 (nvidia_[a-z0-9_]+|torch-[0-9.]+[^ ]*\.whl)" "$LOG" 2>/dev/null | tail -n 1 | cut -d" " -f2)
  [ -n "$TGT" ] || TGT=$L
  HAVE=$(du -sk $DL/$TGT.part* 2>/dev/null | awk "{s+=\$1} END{printf \"%.0f\", s/1024}")
  [ -n "$HAVE" ] || HAVE=0
  # 进程还活着吗
  if pgrep -f "$L" >/dev/null 2>&1 || pgrep -f "multi-dl" >/dev/null 2>&1; then ST="进行中"; else ST="已停止/待重启"; fi
  if [ -n "$TOTMB" ] && [ "$TOTMB" != "0" ]; then
    PCT=$(awk -v h="$HAVE" -v t="$TOTMB" "BEGIN{if(t>0)printf \"%.0f\", h*100/t; else print 0}")
    echo "⬇️ $TGT：已下 ${HAVE}MB / 共 ${TOTMB}MB（${PCT}%）· $ST"
  else
    echo "⬇️ $TGT：已下 ${HAVE}MB · $ST"
  fi
  found=1
done
[ "$found" = "1" ] || echo "⬇️ 当前无进行中的下载"
# NAS 已备份的包
P=-1
for T in $DL/*.tar; do [ -f "$T" ] && { echo "📦 已打包待传：$(basename $T) $(du -h $T 2>/dev/null | cut -f1)"; break; }; done