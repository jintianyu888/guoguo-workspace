#!/bin/bash
# print-toolchain-restore.sh —— 恢复打印影像工具链（2026-10-16 打印组报障）
LOG=/home/j/.openclaw/workspace/state/print-toolchain.log
W=/mnt/c/Windows/System32/wsl.exe
{
  echo "=== START $(date '+%F %T') ==="
  timeout 900 $W -d Ubuntu -u root -- bash -lc "export DEBIAN_FRONTEND=noninteractive; apt-get update -qq 2>&1 | tail -2; apt-get install -y -qq poppler-utils ghostscript imagemagick img2pdf python3-pil 2>&1 | tail -6"
  echo "apt_rc=$?"
  echo "--- 校验 ---"
  for b in img2pdf pdfunite gs convert pdftoppm; do printf '%s: ' $b; command -v $b || echo 缺; done
  /usr/bin/python3 -c 'import PIL,sys;print("PIL",PIL.__version__,"on",sys.executable)'
  echo "=== DONE $(date '+%F %T') ==="
} >> "$LOG" 2>&1
