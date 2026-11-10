#!/usr/bin/env bash
# feishu-allow-id.sh —— 抓出该账号空间的 open_id 候选；默认只打印，不自动加白
# 用法: feishu-allow-id.sh <account>            # 只列候选
#       feishu-allow-id.sh <account> --yes     # 把唯一候选加入白名单
#       feishu-allow-id.sh <account> ou_xxx    # 指定 ID 加入白名单
set -euo pipefail
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
CFG=/home/j/.openclaw/openclaw.json
LOCK=/home/j/.openclaw/workspace/state/work/feishu-config.lock
mkdir -p "$(dirname "$LOCK")"
exec 9>"$LOCK"
flock -n 9 || { echo "另一个飞书配置写入进行中，稍后再试"; exit 5; }
AG="$1"; ARG="${2:-}"
if [ -z "$AG" ]; then echo "用法: $0 <account> [--yes|ou_xxx]"; exit 2; fi
CANDS=$(journalctl --user -u openclaw-gateway --since -60min --no-pager 2>/dev/null | grep -oE "feishu\[$AG\]: (blocked unauthorized sender|received message from) ou_[A-Za-z0-9]+" | grep -oE "ou_[A-Za-z0-9]+" | sort -u || true)
if [ -z "$CANDS" ]; then echo "近60分钟没抓到该账号的 open_id；让对方先发一条消息"; exit 3; fi
echo "候选 open_id（同一个人在本应用空间的 ID）:"; echo "$CANDS" | sed "s/^/  /"
case "$ARG" in
  "") echo "未写入。确认是本人后：$0 $AG --yes  （或指定 $0 $AG ou_xxx）"; exit 0;;
  --yes) COUNT=$(echo "$CANDS" | wc -l); if [ "$COUNT" -ne 1 ]; then echo "候选不唯一($COUNT)，请显式指定 ou_xxx"; exit 4; fi; OU=$(echo "$CANDS");;
  ou_*) OU="$ARG";;
  *) echo "参数无效: $ARG"; exit 2;;
esac
echo "写入白名单: $OU"
cp -a "$CFG" "$CFG.bak-allowid-$(date +%Y%m%d-%H%M%S)"
python3 /home/j/.openclaw/workspace/tools/_feishu_allow.py "$CFG" "$AG" "$OU"
if ! openclaw config validate; then
  cp -a "$BAK" "$CFG"
  echo "❌ config validate 失败，已回滚到 $BAK"; exit 6
fi
printf "%s allow-id %s %s\n" "$(date "+%F %T")" "$AG" "$OU" >> /home/j/.openclaw/workspace/state/work/feishu-allow-ledger.log
echo "插件会热加载；1 分钟内仍被拦则走 tools/restart-gateway.sh 安全重启"
