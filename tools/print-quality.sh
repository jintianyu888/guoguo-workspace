#!/usr/bin/env bash
# print-quality.sh —— 打印质量档位菜单（2026-11-19 主公定：标准/高清/超高清 + 预计耗时）
# 用法: print-quality.sh <文件> [--level std|hd|uhd] [--paper a4|a3] [--pages N] [--dry]
#   标准 std  400dpi 二值  ≈1.5 秒/页（14 页约 20 秒）—— 默认
#   高清 hd   600dpi 二值  ≈3.3 秒/页（14 页约 47 秒）
#   超高清 uhd 1200dpi 二值 ≈11.2 秒/页（14 页约 2 分 37 秒）
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LEVEL=std; PAPER=a4; PAGES=0; DRY=""; SRC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --level) LEVEL="$2"; shift 2;;
    --paper) PAPER="$2"; shift 2;;
    --pages) PAGES="$2"; shift 2;;
    --dry)   DRY="--dry"; shift;;
    --help|-h) sed -n "2,6p" "$0"; exit 0;;
    *) SRC="$1"; shift;;
  esac
done
[ -n "$SRC" ] || { echo "缺文件，用法见 --help"; exit 2; }
case "$LEVEL" in
  std|standard) DPI=400; NAME="标准 400dpi"; PER=1.5;;
  hd|high)      DPI=600; NAME="高清 600dpi"; PER=3.3;;
  uhd|ultra)    DPI=1200; NAME="超高清 1200dpi"; PER=11.2;;
  *) echo "未知档位：$LEVEL（std|hd|uhd）"; exit 2;;
esac
EST=""
if [ "$PAGES" -gt 0 ] 2>/dev/null; then EST=$(awk "BEGIN{printf \"%.0f\", $PAGES*$PER}"); fi
echo "档位：$NAME｜纸型：$PAPER｜预处理约 $PER 秒/页$EST"
echo "说明：预处理在电脑本地跑，跑完才送印；出纸时间另计。"
bash "$DIR/print-score.sh" "$SRC" --dpi "$DPI" --paper "$PAPER" $DRY
