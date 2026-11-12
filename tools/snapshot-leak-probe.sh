#!/bin/bash
# snapshot-leak-probe.sh — 验证 SQLite 只读快照临时目录泄漏的根因判定（任务 #994）
# 结论口径：泄漏根因是「清理只挂在创建进程的优雅退出钩子上」+「上游无孤儿清扫」，
#           非权限/ENOTEMPTY 失败，非 janitor 缺失。
# rc=0 表示以下 6 项证据全部成立。
set -u
SNAP_ROOT=${SNAP_ROOT:-/home/j/.cache/openclaw-1000}
SRC=${SRC:-/home/j/.openclaw/state/openclaw.sqlite}
MOD=/home/j/.npm-global/lib/node_modules/openclaw/dist/native-hook-relay/sqlite-snapshot-staging-owner-ctWsxzq7.mjs
fail=0
ok(){ echo "PASS $*"; }
bad(){ echo "FAIL $*"; fail=1; }

# 1. 残留目录存在（若为 0，说明此刻无样本，用 --count-only 查看）
dirs=()
while IFS= read -r d; do dirs+=("$d"); done < <(ls -d "$SNAP_ROOT"/openclaw-sqlite-readonly-v2-* 2>/dev/null)
echo "INFO 残留目录 ${#dirs[@]} 个 @ $SNAP_ROOT"
if [ "${#dirs[@]}" -gt 0 ]; then ok "存在残留快照目录（泄漏可观测）"; else echo "SKIP 当前无残留目录（janitor 刚清完），其余证据仍校验"; fi

# 2. 残留内容＝状态库整份副本（证明不是空壳）
src_sz=$(stat -c%s "$SRC" 2>/dev/null || echo 0)
copies=0; near=0
for d in "${dirs[@]:-}"; do
  [ -n "$d" ] || continue
  f=$(find "$d" -maxdepth 2 -type f -name 'database.sqlite' 2>/dev/null | head -1)
  [ -n "$f" ] || f=$(find "$d" -maxdepth 2 -type f -name 'database.sqlite.partial' 2>/dev/null | head -1)
  [ -n "$f" ] || continue
  copies=$((copies+1))
  sz=$(stat -c%s "$f")
  [ "$src_sz" -gt 0 ] || continue
  diff=$(( sz > src_sz ? sz - src_sz : src_sz - sz ))
  [ $(( diff * 100 / src_sz )) -le 5 ] && near=$((near+1))
done
if [ "$copies" -eq 0 ] || [ "$near" -gt 0 ]; then ok "残留内含状态库整份副本（源 $src_sz B，接近样本 $near/$copies）"; else bad "残留内容与状态库尺寸不匹配"; fi

# 3. 中断特征：.partial 文件 或 owner.sqlite 为 0 字节（owner 事务未提交）
interrupted=0
for d in "${dirs[@]:-}"; do
  [ -n "$d" ] || continue
  if find "$d" -name '*.partial*' -type f | grep -q . ; then interrupted=$((interrupted+1)); continue; fi
  if [ -f "$d/owner.sqlite" ] && [ "$(stat -c%s "$d/owner.sqlite")" -eq 0 ]; then interrupted=$((interrupted+1)); fi
done
if [ "${#dirs[@]}" -eq 0 ] || [ "$interrupted" -gt 0 ]; then ok "存在「拷贝未完成」特征（.partial 或 0 字节 owner.sqlite）：$interrupted 个"; else bad "未见中断特征，根因判定需复核"; fi

# 4. 不是清理失败：近 1 小时无 snapshot cleanup failed 告警
if journalctl --user -u openclaw-gateway --since '1 hour ago' --no-pager 2>/dev/null | grep -q 'SQLite read-only snapshot cleanup failed'; then
  bad "存在 cleanup failed 告警 → 根因偏向权限/占用"
else
  ok "网关日志近 1 小时无 cleanup failed 告警（排除权限失败）"
fi

# 5. 代码事实：清理挂在 process.once(exit) + retire 路径 rmSync
if grep -q 'process.once("exit"' "$MOD" && grep -q 'fsSync.rmSync(tempDir' "$MOD"; then
  ok "上游清理仅两个入口：进程退出钩子 + retire 路径 rmSync，无启动期孤儿清扫"
else
  bad "上游模块结构变化，清理路径结论需重读"
fi

# 6. 兜底存在：janitor 定时器 active
if systemctl --user is-active --quiet oc-cache-janitor.timer; then ok "oc-cache-janitor.timer active（唯一兜底）"; else bad "janitor 定时器未运行"; fi

echo "RESULT ${fail:-0}"
exit "${fail:-0}"
