#!/bin/bash
# migrate-ws-checksum.sh —— 全树 sha256 比对（双审要求的强校验）
set -uo pipefail
SRC=/home/j/openclaw-workspaces
DST=/home/j/openclaw-workspaces
W=/home/j/.openclaw/workspace
OUT=$W/state/work/migrate-checksum-report.txt
LOG=$W/state/work/migrate-checksum.log
say(){ echo "[$(date "+%F %T")] $*" | tee -a "$LOG"; }
for i in $(seq 1 120); do
  systemctl --user is-active migrate-ws-copy.service >/dev/null 2>&1 || break
  sleep 30
done
say "复制单元已结束，开始全树哈希（两侧并行）"
( cd "$SRC" && find . -type f -print0 2>/dev/null | sort -z | xargs -0 -r sha256sum ) > /tmp/ws-src.sha 2>/dev/null &
( cd "$DST" && find . -type f -print0 2>/dev/null | sort -z | xargs -0 -r sha256sum ) > /tmp/ws-dst.sha 2>/dev/null &
wait
S=$(wc -l < /tmp/ws-src.sha); D=$(wc -l < /tmp/ws-dst.sha)
DIFF=$(diff <(cut -c1-64,67- /tmp/ws-src.sha) <(cut -c1-64,67- /tmp/ws-dst.sha) 2>/dev/null | grep -c "^[<>]")
{ echo "时间 $(date "+%F %T")"; echo "源文件数=$S 目标文件数=$D"; echo "哈希差异行数=$DIFF"; } > "$OUT"
diff <(cut -c1-64,67- /tmp/ws-src.sha) <(cut -c1-64,67- /tmp/ws-dst.sha) 2>/dev/null | head -20 >> "$OUT"
say "全树比对完成：源 $S / 目标 $D / 差异 $DIFF"
if [ "$DIFF" = "0" ] && [ "$S" = "$D" ]; then V="一致"; else V="不一致"; fi
timeout 60 bash "$W/tools/notify.sh" "🔐 工作区全树哈希比对：$V（源 $S 文件 / 目标 $D 文件 / 差异行 $DIFF）。报告 state/work/migrate-checksum-report.txt" >/dev/null 2>&1 || true
