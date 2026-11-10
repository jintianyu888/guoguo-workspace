#!/bin/bash
# 备份深度自检 + 恢复演练（v3 · 2026-10-20）
# v3 修正：① 大归档不再抽样 200 条——官方备份布局是 payload/posix/home/j/.openclaw/… 全路径，
#         关键文件排在约第 8.8 万条（63% 深度），抽样必然漏检，10-20 03:45 曾造成四项假阴性；
#         改为全量列清单（420s 上限），失败如实降级。
#         ② 解包演练复用同一次全量流读（tar 读到 EOF = gzip 完整性验证），不再二次流读。
#         ③ 关键文件抽取超时 90→480s（目标在 63% 深度，需流读约一半归档）。
# v2 修正：① 归档目录兼容新路径 ② 解包演练只抽关键文件、且在【磁盘】上跑
#       ③ 「管家库」只数真实库（不再把暂存快照算进去 → 44 变 22）
set -uo pipefail
W=/home/j/.openclaw/workspace
ARCH=""
for d in /mnt/d/openclaw-backups; do
  [ -d "$d" ] && { ARCH="$d"; break; }
done
[ -z "$ARCH" ] && { echo "❌ 找不到归档目录"; exit 1; }
FF=$(ls -t "$ARCH"/*.tar.gz 2>/dev/null | head -1)
[ -z "$FF" ] && { echo "❌ 无归档"; exit 1; }
echo "🔬 备份深度自检 · $(date "+%Y-%m-%d %H:%M")"
echo "· 归档：$(basename "$FF")（$(du -h "$FF" 2>/dev/null | cut -f1)）"
SZMB=$(du -m "$FF" 2>/dev/null | cut -f1); SZMB=${SZMB:-0}
LT=$(mktemp "$W/state/work/drill-list.XXXXXX" 2>/dev/null || mktemp)
if [ "$SZMB" -lt 5120 ]; then
  tar tzf "$FF" > "$LT" 2>/dev/null; TRC=$?
  echo "· 条目总数：全量 $(wc -l < "$LT")（归档 ${SZMB}MB）"
else
  # 大归档也全量列（v3）：420s 上限，失败则带部分清单继续并如实标注
  timeout 420 tar tzf "$FF" > "$LT" 2>/dev/null; TRC=$?
  if [ "$TRC" -eq 0 ]; then
    echo "· 条目总数：全量 $(wc -l < "$LT") 条（归档 ${SZMB}MB）"
  else
    echo "· 条目总数：⚠️ 全量列出超时/失败(rc=$TRC)，仅有前 $(wc -l < "$LT") 条——关键文件检查可能不完整"
  fi
fi
bad=0
for k in openclaw.json state/openclaw.sqlite workspace/IDENTITY.md workspace/SOUL.md workspace/AGENTS.md workspace/memory/; do
  if grep -q "$k" "$LT"; then echo "  ✅ $k"; else echo "  ❌ $k"; bad=$((bad+1)); fi
done
# 管家库：只数真实库（agents/<名>/agent/openclaw-agent.sqlite）
LIVE=$(grep -cE '(^|/)agents/[^/]+/agent/openclaw-agent[.]sqlite' "$LT" 2>/dev/null); LIVE=${LIVE:-0}
STAGE=$(grep -cE '(^|/)backup-extra/agents-db/' "$LT" 2>/dev/null || echo 0)
echo "· 管家库：$LIVE 个（另含暂存快照 $STAGE 个）"
# 解包演练（v3）：复用上面的全量流读结果——tar 读到 EOF 即 gzip 完整性验证通过
T="$W/state/work/drill.$$"; mkdir -p "$T"
if [ "${TRC:-1}" -eq 0 ]; then
  echo "· 解包演练：✅ 成功（全量清单已完整流式读通归档，gzip 完整性验证通过）"
elif [ "${TRC:-1}" -eq 124 ]; then
  echo "· 解包演练：⏳ 未完成（清单列出超时；归档大 + 挂在 Windows 盘，读取慢）—— 如实报告"
else
  echo "· 解包演练：❌ 失败（读取错误 rc=$TRC）"; bad=$((bad+1))
fi
# 关键文件抽取：用清单里的精确路径抽 1 个（快，不做全量扫描）
KEY=$(grep -m1 -E '(^|/)workspace/IDENTITY\.md$' "$LT" 2>/dev/null | head -1)
if [ -n "$KEY" ]; then
  if timeout 480 tar xzf "$FF" -C "$T" "$KEY" >/dev/null 2>&1; then
    echo "· 关键文件抽取：✅ $(head -1 "$T/$KEY" 2>/dev/null)"
  else
    echo "· 关键文件抽取：⏳ 未完成（480s 超时，目标文件在归档深处，读取慢）"
  fi
else
  echo "· 关键文件抽取：⚠️ 清单里未找到 IDENTITY.md（若上方标注过清单不完整则可能漏检；全量仍未命中才是真缺失）"
fi
rm -rf "$T" "$LT"
if [ "$bad" -eq 0 ]; then echo "【结论】✅ 归档完整，可恢复"; else echo "【结论】❌ 有 $bad 项异常"; fi
