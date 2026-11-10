#!/usr/bin/env bash
# print-score.sh —— 乐谱/线稿【默认】打印流程（高清 600dpi 二值 A4 -> IPP 631 直投）
# 2026-10-03 主公确认：此模式比直投原图清晰，定为乐谱默认。
# 用法: bash print-score.sh <源.pdf|图片> [--dpi 600] [--paper a4|a3] [--no-fill] [--dry]
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$#" -lt 1 ]; then echo "usage: bash print-score.sh <file> [--dpi N] [--paper a4] [--no-fill] [--dry]"; exit 2; fi
SRC="$1"; shift
PAPER=a4; DPI=600; EXTRA=""; DRY=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --paper) PAPER="$2"; shift 2;;
    --dpi)   DPI="$2";   shift 2;;
    --no-fill) EXTRA="$EXTRA --no-fill"; shift;;
    --dry)   DRY="--dry"; shift;;
    *) shift;;
  esac
done
OUT="/home/j/.openclaw/workspace/state/tmp/score-hi-$$.pdf"
python3 "$DIR/print-hires-pdf.py" "$SRC" --dpi "$DPI" --paper "$PAPER" $EXTRA --out "$OUT"
python3 "$DIR/print-ipp.py" "$OUT" $DRY
