#!/bin/bash
# nas-config.sh —— NAS 路径唯一真源（2026-11-02 迁移到新 NAS 后建立）
#
# 背景：老 NAS（192.168.1.5）已断联，全部改为已挂载的 CIFS：//192.168.1.109/home → /mnt/nas
# 2026-11-02 22:20 更新：新 NAS 的 SSH 已打通（guoguonas@192.168.1.109:2222，密钥 ~/.ssh/nas_guoguo），
#   并在 ~/.ssh/config 建了别名 `nas`。备份主链（本文件使用者）仍走 CIFS；其余 27 个运维脚本走 `ssh nas`。
#   新脚本二选一：优先 CIFS（快、无 sshd 依赖）；需要远端 rm/df/du 语义时用 `ssh nas`。
#
# 用法：source 本文件，然后使用下面的变量与 nas_guard。
# 注意：/mnt/nas 是 nofail 挂载，掉线时目录会消失；nas_guard 必须在使用前调用。

NAS_MOUNT=/mnt/nas
NAS_ROOT=$NAS_MOUNT/archive/jinyu
NAS_ARCHIVES=$NAS_ROOT/openclaw-archives
NAS_TIER1=$NAS_ROOT/migrated-20261102/openclaw-backups-tier1
NAS_TIER2=$NAS_ROOT/migrated-20261102/openclaw-backups-tier2
NAS_REPOS=$NAS_ROOT/migrated-20261102/openclaw-repos
NAS_BACKUPGIT=$NAS_ROOT/migrated-20261102/openclaw-backup.git
NAS_TRASH=$NAS_ROOT/migrated-20261102/openclaw-trash

# nas_guard [目录...] —— 校验挂载、目录存在、并做一次写探针（2026-11-02 三审加入）
# 失败返回 1 并打印明确原因。
# 绝不退化成"写本地目录"：那会静默产生假备份，是最危险的失败模式。
nas_guard() {
  if ! mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
    echo "NAS_GUARD_FAIL: $NAS_MOUNT 未挂载（nofail 挂载可能已掉），拒绝继续" >&2
    return 1
  fi
  local d
  for d in "$@"; do
    if [ ! -d "$d" ]; then
      echo "NAS_GUARD_FAIL: 目录不存在 $d" >&2
      return 1
    fi
  done
  # 写探针：cifs 会出现"挂载还在但写入卡死/只读"的半死状态，mountpoint 查不出来。
  # 用 3 秒超时兜住，避免卡住整个备份任务。
  local probe="$NAS_MOUNT/.nas-guard-probe.$$"
  if ! timeout 3 sh -c ": > \"\$1\" && rm -f \"\$1\"" _ "$probe" 2>/dev/null; then
    echo "NAS_GUARD_FAIL: 写探针失败（$NAS_MOUNT 可能只读或挂载半死）" >&2
    rm -f "$probe" 2>/dev/null
    return 1
  fi
  return 0
}
