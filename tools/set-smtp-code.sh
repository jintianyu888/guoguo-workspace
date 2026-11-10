#!/bin/bash
# set-smtp-code.sh —— 交互式录入 163 SMTP 授权码（不回显、不落日志、不进聊天）
set -u
read -rsp "请粘贴 163 SMTP 授权码，回车结束（输入不回显）: " CODE; echo
if [ -z "${CODE:-}" ]; then echo "空值，已取消"; exit 1; fi
printf "%s" "$CODE" | openclaw secrets store set SMTP_163_AUTH --kind env --value-file - >/dev/null 2>&1
rc=$?; unset CODE
if [ $rc -eq 0 ]; then echo "✅ 已保存 env 条目 SMTP_163_AUTH（可被发信脚本读取）"; else echo "❌ 保存失败 rc=$rc"; fi
exit $rc