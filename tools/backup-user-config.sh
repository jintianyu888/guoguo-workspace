#!/usr/bin/env bash
# backup-user-config.sh —— 用户级配置小备份（2026-10-03 补，审计建议③）
# 覆盖：.npmrc / .gitconfig / .bashrc / .profile / .ssh 配置（不含私钥正文→私钥另走 gpg 加密包）
set -u
TS=$(date +%Y%m%d-%H%M); OUT=/mnt/d/openclaw-backups/user-config
mkdir -p "$OUT" 2>/dev/null || true
T="$OUT/user-config-$TS.tar.gz"
cd /home/j || exit 1
SRC=()
for f in .npmrc .gitconfig .bashrc .profile .ssh/config .ssh/known_hosts; do
  [ -e "/home/j/$f" ] && SRC+=("$f")
done
# 2026-10-28 修：缺失文件（如 .gitconfig）会让 tar 整体 rc=2 导致备份全灭 → 只打包存在的文件
tar czf "$T" "${SRC[@]}" 2>"$OUT/.uc-err.log"; TRC=$?
# 2026-10-27 审查#：tar 报错曾被 2>/dev/null 吞掉，残缺包也算 OK；改为看退出码（GNU tar: >=2 为致命）
if [ "$TRC" -ge 2 ] || [ ! -s "$T" ]; then echo "FAIL 打包失败 rc=$TRC（详见 $OUT/.uc-err.log）"; exit 1; fi
if [ -s "$T" ]; then echo "OK $(du -h "$T" | cut -f1) $T"; fi
ls -t "$OUT"/user-config-*.tar.gz 2>/dev/null | tail -n +6 | while read -r f; do rm -f "$f"; done
echo "保留最近 5 份"