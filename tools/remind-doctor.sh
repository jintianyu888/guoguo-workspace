#!/bin/bash
# remind-doctor.sh —— 提醒主公回电脑后要做的两件事（系统修复 / 整机镜像）；任务关了就不再打扰
set -u
W=/home/j/.openclaw/workspace
OUT=$(python3 - <<'PY'
import json
d=json.load(open('/home/j/.openclaw/workspace/state/tasks/tasks.json',encoding='utf-8'))
openT=[i['title'] for i in d['items'] if i.get('status') in ('open','in_progress')]
a=any('修复系统' in t for t in openT)
b=any('整机镜像' in t for t in openT)
print(('%s|%s') % ('1' if a else '0', '1' if b else '0'))
PY
)
A=$(echo "$OUT" | cut -d"|" -f1); B=$(echo "$OUT" | cut -d"|" -f2)
if [ "$A" = "1" ] && [ "$B" = "1" ]; then
  bash "$W/tools/notify.sh" "⏰ 回来要做的两件事" "① 系统修复：openclaw update repair  ② 整机镜像：wsl --shutdown 后 wsl --export Ubuntu E:\wsl-backup\ubuntu-20261018.tar（命令见对话）"
elif [ "$A" = "1" ]; then
  bash "$W/tools/notify.sh" "⏰ 提醒：系统修复还没做" "回到电脑后执行：openclaw update repair（先备份 openclaw.json）"
elif [ "$B" = "1" ]; then
  bash "$W/tools/notify.sh" "⏰ 提醒：整机镜像还没导出" "回到电脑后：wsl --shutdown 再 wsl --export Ubuntu E:\wsl-backup\ubuntu-20261018.tar"
fi