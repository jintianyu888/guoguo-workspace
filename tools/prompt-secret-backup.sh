#!/usr/bin/env bash
# 备份管家 App Secret 掩码录入（2026-10-31）
# 输入不回显、不入日志、不进聊天；直接写入 secret store
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
NAME=FEISHU_BACKUP_APP_SECRET
echo "============================================="
echo " 备份管家 · 飞书 App Secret 录入"
echo " appId: cli_aa6fdc3f53781c1a"
echo " 存储名: $NAME"
echo " 输入时不会显示字符，粘贴后直接回车"
echo "============================================="
printf 'App Secret: '
IFS= read -r -s SEC || { echo; echo '已取消'; exit 1; }
echo
if [ -z "${SEC:-}" ]; then echo '未输入，已取消'; exit 1; fi
if ! printf '%s' "$SEC" | openclaw secrets store set "$NAME" --kind secret --value-file - 2>/tmp/secret-err.log; then
  echo "写入失败：$(cat /tmp/secret-err.log | tail -3)"
  unset SEC; exit 2
fi
unset SEC
echo '✅ 已写入 secret store（明文不留存于任何文件）'
echo "校验: $(openclaw secrets store list 2>/dev/null | grep -c "^$NAME " || true) 条记录（1=成功）"
echo
echo '可以关闭此窗口了，果果会继续配置通道。'
exit 0
