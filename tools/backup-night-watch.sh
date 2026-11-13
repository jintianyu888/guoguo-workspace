#!/usr/bin/env bash
# 盯今晚(2026-11-13 01:00)全量备份的结局：打包/D 复制/E 镜像/推送 各自成败，推飞书一条
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/bk-run.log
DAY=${1:-2026-11-13}
end=""
for i in $(seq 1 120); do
  if grep -q "推送完成 rc=0\|推送未全成功 rc=\|复制到 D 失败" "$LOG" 2>/dev/null; then end="1"; fi
  if [ -n "$end" ] && grep -q "^=== $DAY .*打包完成" "$LOG" 2>/dev/null; then break; fi
  sleep 120
done
seg=$(awk -v d="=== $DAY" 'index($0,d){p=1} p' "$LOG" 2>/dev/null | tail -c 120000)
size=$(grep -oE "打包完成 .* [0-9]+ 字节" "$LOG" 2>/dev/null | tail -1)
xok=$(echo "$seg" | grep -c "已落 X 盘")
dfail=$(echo "$seg" | grep -c "复制到 D 失败")
emir=$(echo "$seg" | grep -c "E/H 镜像与校验完成")
efail=$(echo "$seg" | grep -c "E/H 镜像或校验失败")
push=$(echo "$seg" | grep -E "推送完成 rc=|推送未全成功 rc=" | tail -1)
part=$(ls -l /mnt/e/openclaw-backups/*.part 2>/dev/null | awk '{s+=$5} END{printf "%.0f", s/1073741824}')
dfree=$(df -h /mnt/d 2>/dev/null | awk 'NR==2{print $4}')
xtop=$(ls -lt /mnt/x/openclaw-backups/*.tar.gz 2>/dev/null | head -1 | awk '{print $5, $6, $7, $8, $9}')
{
  echo "今晚备份结局："
  echo "- 打包：$size"
  echo "- X 盘落盘：$xok（1=成功）"
  echo "- 复制到 D：$([ "$dfail" -gt 0 ] && echo 失败 || echo 成功或未报错)，D 剩余 $dfree"
  echo "- E/H 镜像：完成 $emir / 失败 $efail"
  echo "- 推送结论：${push:-未见结论行}"
  echo "- 残留 .part：${part:-0} GB"
  echo "- X 盘最新归档：$xtop"
} > /tmp/bk-night-msg.txt
bash "$W/tools/notify.sh" "$(cat /tmp/bk-night-msg.txt)" "🌙 夜间备份结果" 2>/dev/null || true
