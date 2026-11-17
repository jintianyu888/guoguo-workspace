#!/bin/bash
# inbound-latest.sh v1.0 (2026-11-17) —— 找最近收到的飞书附件（图片/语音/文件）落盘路径
# 用法: bash tools/inbound-latest.sh [数量] [类型过滤: jpg|png|ogg|pdf|空=全部]
# 说明: 附件会同时出现在中心目录 ~/.openclaw/media/inbound 和 各 agent 工作区的 media/inbound/openclaw-staged-*/ 下。
#       同名文件以 input-<uuid>.<ext> 形式存在子目录里，直接 ls 顶层目录是找不到的（模型管家踩过）。
set -u
N="${1:-5}"
PAT="${2:-}"
WS_ROOT="/home/j/.openclaw"
find "$WS_ROOT/media/inbound" "$WS_ROOT"/workspace*/media/inbound -type f \
  \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' -o -name '*.webp' -o -name '*.ogg' -o -name '*.mp3' -o -name '*.m4a' -o -name '*.pdf' -o -name '*.docx' -o -name '*.xlsx' \) \
  -printf '%T@ %s %p\n' 2>/dev/null \
  | sort -rn | head -n "$N" \
  | while read -r ts size path; do
      [ -n "$PAT" ] && case "$path" in *."$PAT"|*."$PAT".*) ;; *) continue ;; esac
      printf '%s  %8s B  %s\n' "$(date -d "@${ts%.*}" '+%m-%d %H:%M')" "$size" "$path"
    done

