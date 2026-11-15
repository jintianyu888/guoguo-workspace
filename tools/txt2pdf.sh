#!/bin/sh
# txt2pdf.sh — 纯文本→A4 PDF（中文 13pt、页脚页码），依赖本机 playwright chromium
# 用法: bash tools/txt2pdf.sh IN.txt OUT.pdf [--size 13]
set -e
exec node "$(dirname "$0")/txt2pdf.js" "$@"
