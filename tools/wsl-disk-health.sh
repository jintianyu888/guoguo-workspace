#!/usr/bin/env bash
# wsl-disk-health.sh — WSL 盘位体检（只读）v2 · 2026-10-22
# 背景：2026-10-22 Ubuntu 发行版从 D:\WSL\Ubuntu 迁到 X:\WSL\Ubuntu（独立 NVMe）
# 立场：只体检、只报告 —— 不改配置 / 不迁移 / 不重启 / 不 kill / 不删
# 用法：sh tools/wsl-disk-health.sh [--json] [--quiet] [--deep]
#   --json   输出 JSON（给自动化消费）
#   --quiet  只输出结论行
#   --deep   加扫全盘 .vhdx 副本（慢，默认不跑）
# 退出码：0=全通过  1=有警告  2=有失败
set -uo pipefail

W=/home/j/.openclaw/workspace
PROBE="$W/tools/.wsl-health-probe.ps1"
PS_EXE=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
WSL_EXE=/mnt/c/Windows/System32/wsl.exe
EXPECT_BASE='X:\WSL\Ubuntu'
EXPECT_DRIVE=X
MOUNT=/mnt/$(echo "$EXPECT_DRIVE" | tr 'A-Z' 'a-z')

MODE=human
DEEP=0
for a in "$@"; do
  case "$a" in
    --json)  MODE=json ;;
    --quiet) MODE=quiet ;;
    --deep)  DEEP=1 ;;
  esac
done

ENT=$(mktemp "$W/state/tmp/wsl-health-ent.XXXXXX")
KV=$(mktemp "$W/state/tmp/wsl-health-kv.XXXXXX")
trap 'rm -f "$ENT" "$KV"' EXIT

PASS=0; WARN=0; FAIL=0; NOTE=0

kv()  { grep -m1 "^$1=" "$KV" 2>/dev/null | cut -d= -f2- | tr -d '\r'; }
kva() { grep "^$1=" "$KV" 2>/dev/null | cut -d= -f2- | tr -d '\r'; }
sec() { [ "$MODE" = human ] && printf '\n\033[1m【%s】\033[0m\n' "$1"; return 0; }
add() { # lvl item detail
  local lvl="$1" item="$2" det="$3" mark
  printf '%s\t%s\t%s\n' "$lvl" "$item" "$det" >> "$ENT"
  case "$lvl" in
    PASS) PASS=$((PASS+1)); mark='✅' ;;
    WARN) WARN=$((WARN+1)); mark='⚠️' ;;
    FAIL) FAIL=$((FAIL+1)); mark='❌' ;;
    *)    NOTE=$((NOTE+1)); mark='ℹ️' ;;
  esac
  [ "$MODE" = human ] && printf '  %s %-30s %s\n' "$mark" "$item" "$det"
  return 0
}
num() { case "$1" in ''|*[!0-9.]*) echo 0;; *) echo "$1";; esac; }

# ---------------- 0. 取数 ----------------
if [ -f "$PS_EXE" ] && [ -f "$PROBE" ]; then
  PWS=$(wslpath -w "$PROBE" 2>/dev/null || echo "$PROBE")
  if [ "$DEEP" = 1 ]; then
    timeout 300 "$PS_EXE" -NoProfile -ExecutionPolicy Bypass -File "$PWS" -Deep 2>/dev/null | tr -d '\r' > "$KV"
  else
    timeout 120 "$PS_EXE" -NoProfile -ExecutionPolicy Bypass -File "$PWS" 2>/dev/null | tr -d '\r' > "$KV"
  fi
fi
if [ ! -s "$KV" ]; then
  echo "❌ 取不到 Windows 侧数据（PowerShell 不可用或超时）" >&2
  exit 2
fi

if [ "$MODE" = human ]; then
  echo "🩺 WSL 盘位体检 · $(date '+%Y-%m-%d %H:%M:%S')  [只读]"
  echo "   期望发行版位置：$EXPECT_BASE"
fi

# ---------------- A. 盘位 ----------------
sec "A. 目标盘位"
FREE=$(num "$(kv VOL_${EXPECT_DRIVE}_FREEGB)")
USED=$(num "$(kv VOL_${EXPECT_DRIVE}_USEDGB)")
FSTYPE=$(kv VOL_${EXPECT_DRIVE}_FS)
DISKNUM=$(kv VOL_${EXPECT_DRIVE}_DISKNUM)
DMODEL=$(kv DISK_${DISKNUM}_MODEL)
DBUS=$(kv DISK_${DISKNUM}_BUS)
DHEALTH=$(kv DISK_${DISKNUM}_HEALTH)
DDISKGB=$(kv DISK_${DISKNUM}_SIZEGB)
CDISKNUM=$(kv VOL_C_DISKNUM)

if [ -d "$MOUNT" ]; then
  add PASS "目标盘 ${EXPECT_DRIVE}: 挂载" "$MOUNT 正常"
else
  add FAIL "目标盘 ${EXPECT_DRIVE}: 挂载" "$MOUNT 不存在！"
fi

if   awk -v f="$FREE" 'BEGIN{exit !(f<50)}';  then add FAIL "目标盘剩余空间" "${FREE}G —— 低于 50G 红线"
elif awk -v f="$FREE" 'BEGIN{exit !(f<200)}'; then add WARN "目标盘剩余空间" "${FREE}G —— 偏低（<200G 预警线）"
else add PASS "目标盘剩余空间" "${FREE}G 可用（已用 ${USED}G）"
fi

if [ -n "$DMODEL" ]; then
  add PASS "物理盘信息" "Disk${DISKNUM} ${DMODEL} / ${DBUS} / ${DDISKGB}G / ${DHEALTH}"
else
  add WARN "物理盘信息" "未取到（PowerShell 权限或结构变化）"
fi

case "$DBUS" in
  USB) add WARN "盘位类型" "USB 外接盘 —— 掉电/休眠可能损坏 vhdx，建议换内置盘" ;;
  "")  add WARN "盘位类型" "未知" ;;
  *)   add PASS "盘位类型" "${DBUS}（非 USB 外接）" ;;
esac

if [ -n "$DHEALTH" ] && [ "$DHEALTH" != "Healthy" ]; then
  add FAIL "磁盘健康" "$DHEALTH（不是 Healthy）"
elif [ -n "$DHEALTH" ]; then
  add PASS "磁盘健康" "Healthy"
fi

case "$FSTYPE" in
  NTFS|ReFS) add PASS "文件系统" "$FSTYPE" ;;
  *) add WARN "文件系统" "${FSTYPE:-未知}（建议 NTFS/ReFS）" ;;
esac

if [ -n "$CDISKNUM" ] && [ "$CDISKNUM" = "$DISKNUM" ]; then
  add WARN "与系统盘关系" "与 C:（系统盘）同一物理盘 Disk${DISKNUM} —— 盘坏则整机全没"
elif [ -n "$CDISKNUM" ]; then
  add PASS "与系统盘关系" "独立物理盘（Disk${DISKNUM} ≠ 系统盘 Disk${CDISKNUM}）"
fi

# ---------------- B. 发行版注册 ----------------
sec "B. 发行版注册"
BASE=$(kv LXSS_BASEPATH)
VER=$(kv LXSS_VERSION)
NAME=$(kv LXSS_NAME)
if [ "$BASE" = "$EXPECT_BASE" ]; then
  add PASS "注册 BasePath" "$BASE（与期望一致）"
elif [ -n "$BASE" ]; then
  add FAIL "注册 BasePath" "$BASE  ≠ 期望 $EXPECT_BASE"
else
  add FAIL "注册 BasePath" "未取到"
fi
if [ "$VER" = 2 ]; then add PASS "WSL 版本" "Version=2 (WSL2)"; else add WARN "WSL 版本" "Version=${VER:-未知}"; fi
add PASS "发行版名" "${NAME:-未知}"

if [ -f "$WSL_EXE" ]; then
  WLIST=$(timeout 30 "$WSL_EXE" -l -v 2>/dev/null | iconv -f UTF-16LE -t UTF-8 2>/dev/null | tr -d '\r\0﻿')
  if echo "$WLIST" | grep -qi "Running"; then
    add PASS "运行状态" "Running"
  else
    add WARN "运行状态" "未在 Running（$(echo "$WLIST" | tr -s ' \n' ' ' | cut -c1-60)）"
  fi
else
  add WARN "运行状态" "wsl.exe 不可达"
fi

# ---------------- C. 虚拟磁盘 ----------------
sec "C. 虚拟磁盘 (ext4.vhdx)"
VEX=$(kv VHDX_EXISTS)
VSZ=$(kv VHDX_SIZEGB)
VMT=$(kv VHDX_MTIME)
VSP=$(kv VHDX_SPARSE)
VFILE="$MOUNT/WSL/Ubuntu/ext4.vhdx"

if [ "$VEX" = 1 ]; then
  add PASS "vhdx 存在" "$EXPECT_BASE\\ext4.vhdx  ${VSZ}G"
else
  add FAIL "vhdx 存在" "$EXPECT_BASE 下找不到 ext4.vhdx"
fi

if [ -n "$VMT" ]; then
  MTIME_S=$(date -d "$VMT" +%s 2>/dev/null || echo 0)
  AGE=$(( $(date +%s) - MTIME_S ))
  if [ "$AGE" -ge 0 ] && [ "$AGE" -lt 7200 ]; then
    add PASS "最近写入" "$VMT（${AGE}s 前）—— 盘是活的"
  else
    add WARN "最近写入" "$VMT（$((AGE/3600)) 小时前）—— 盘可能没在用"
  fi
fi

if [ "$VSP" = 1 ]; then
  add PASS "稀疏属性" "SparseFile 已开（删除可自动回收）"
elif [ "$VSP" = 0 ]; then
  add WARN "稀疏属性" "非稀疏 —— 删除不回收空间，需 wsl --shutdown 后 compact"
fi

# .wslconfig：sparseVhd 开关 + swapFile 位置
WSLCONF=$(ls /mnt/c/Users/*/.wslconfig 2>/dev/null | head -1)
if [ -n "$WSLCONF" ]; then
  if grep -qiE 'sparseVhd[[:space:]]*=[[:space:]]*true' "$WSLCONF"; then
    add PASS ".wslconfig sparseVhd" "true（新建盘自动稀疏）"
  else
    add WARN ".wslconfig sparseVhd" "未开 —— 导入/新建的 vhdx 默认非稀疏"
  fi
  SWAPF=$(grep -iE '^[[:space:]]*swapFile=' "$WSLCONF" | head -1 | cut -d= -f2- | tr -d '\r')
  if [ -n "$SWAPF" ]; then
    SWAPW=$(printf '%s' "$SWAPF" | sed 's/\\/\//g; s/^X:/\/mnt\/x/I; s/^D:/\/mnt\/d/I; s/^E:/\/mnt\/e/I; s/^H:/\/mnt\/h/I')
    if [ -f "$SWAPW" ]; then
      add PASS "swapFile 位置" "$SWAPF（在位，$(du -h "$SWAPW" 2>/dev/null | cut -f1)）"
    elif [ "$(wc -l < /proc/swaps 2>/dev/null)" -gt 1 ]; then
      add NOTE "swapFile 位置" "$SWAPF 声明在 $SWAPW，但盘上无此文件；swap 实际由 WSL 内部提供（/proc/swaps 有条目）—— 声明可能未生效"
    else
      add WARN "swapFile 位置" "$SWAPF 声明在 $SWAPW，但文件不在，且无 swap 生效"
    fi
  else
    add NOTE "swapFile" ".wslconfig 未指定 swapFile（走默认盘）"
  fi
fi

if [ -f "$VFILE" ]; then
  APP=$(du -m --apparent-size "$VFILE" 2>/dev/null | cut -f1)
  ACT=$(du -m "$VFILE" 2>/dev/null | cut -f1)
  USEDM=$(( $(df -k / | tail -1 | awk '{print $3}') / 1024 ))
  if [ -n "$APP" ] && [ -n "$ACT" ] && [ "$ACT" -gt 0 ]; then
    RATIO=$(awk -v a="$APP" -v b="$ACT" 'BEGIN{printf "%.2f", a/b}')
    if awk -v r="$RATIO" 'BEGIN{exit !(r>1.2)}'; then
      add WARN "vhdx 膨胀比" "表观 ${APP}M / 实占 ${ACT}M = ${RATIO}x（有空间未回收）"
    else
      add PASS "vhdx 膨胀比" "表观 ${APP}M / 实占 ${ACT}M = ${RATIO}x"
    fi
    SLACK=$((ACT - USEDM))
    if [ "$SLACK" -gt 10240 ]; then
      add WARN "可回收空间" "vhdx 多占约 $((SLACK/1024))G（内部已用 $((USEDM/1024))G）"
    fi
  fi
fi

# ---------------- C2. 回收链路 · 时间基准 · 宿主安全 ----------------
sec "C2. 回收链路 · 时间基准 · 宿主安全"
TRIM=$(kv TRIM_NTFS)
case "$TRIM" in
  0) add PASS "NTFS TRIM 策略" "DisableDeleteNotify=0（宿主层 TRIM 已启用）" ;;
  1) add WARN "NTFS TRIM 策略" "DisableDeleteNotify=1（TRIM 被禁，vhdx 只会长不会缩）" ;;
  *) add NOTE "NTFS TRIM 策略" "读不到（需管理员？）" ;;
esac
if grep -qE " / .*discard" /proc/mounts; then
  add PASS "根 fs discard" "挂载带 discard（内核会下发放弃请求）"
else
  add WARN "根 fs discard" "根 fs 挂载未带 discard —— 内核回收传不到宿主"
fi
DBZ=$(cat /sys/block/sdd/queue/discard_max_bytes 2>/dev/null)
[ -n "$DBZ" ] && add PASS "块设备 discard 上限" "${DBZ} 字节"
if systemctl is-enabled fstrim.timer >/dev/null 2>&1; then
  add NOTE "fstrim.timer" "已启用，但 WSL 内通常不排程（$(systemctl list-timers fstrim.timer --no-pager 2>/dev/null | tail -1 | tr -s ' ' | cut -c1-36)）"
else
  add WARN "fstrim.timer" "未启用"
fi
WINT=$(timeout 20 "$PS_EXE" -NoProfile -Command "[DateTimeOffset]::Now.ToUnixTimeSeconds()" 2>/dev/null | tr -d '\r')
if [ -n "$WINT" ]; then
  DRIFT=$(( $(date +%s) - WINT )); [ "$DRIFT" -lt 0 ] && DRIFT=$(( -DRIFT ))
  if   [ "$DRIFT" -gt 300 ]; then add FAIL "时钟漂移 WSL↔Win" "${DRIFT}s（>5 分钟，会打乱 01:00 备份与 cron）"
  elif [ "$DRIFT" -gt 120 ]; then add WARN "时钟漂移 WSL↔Win" "${DRIFT}s（>2 分钟）"
  else add PASS "时钟漂移 WSL↔Win" "${DRIFT}s"; fi
fi
P9OK=1; P9DET=""
for m in d e h x; do
  T0=$(date +%s%N); timeout 5 stat -c '%s' "/mnt/$m" >/dev/null 2>&1 && R=OK || { R=TIMEOUT; P9OK=0; }
  T1=$(date +%s%N); P9DET="$P9DET /mnt/$m:${R}($(( (T1-T0)/1000000 ))ms)"
done
if [ "$P9OK" = 1 ]; then add PASS "9p 挂载探活" "$P9DET"; else add FAIL "9p 挂载探活" "$P9DET"; fi
IOERR=$(dmesg 2>/dev/null | grep -ciE "i/o error|buffer i/o|EXT4-fs error")
if [ "${IOERR:-0}" -gt 0 ]; then add FAIL "内核 I/O 错误" "dmesg 有 $IOERR 条 I/O/EXT4 错误"; else add PASS "内核 I/O 错误" "0 条（无脏卸载迹象）"; fi
DEX=$(kva DEFENDER_EXCL | tr '\n' ' ')
case "$DEX" in
  *UNAVAILABLE*) add NOTE "Defender 排除项" "读不到（Defender 服务未运行/已禁用）" ;;
  "") add WARN "Defender 排除项" "无排除项 —— 实时扫描会拖慢 vhdx 读写" ;;
  *) if echo "$DEX" | grep -qi 'WSL'; then add PASS "Defender 排除项" "已含 WSL 目录（$DEX）"; else add WARN "Defender 排除项" "未排除 WSL 目录（$DEX）"; fi ;;
esac
NSS=$(kv NTFS_SECTOR); NSC=$(kv NTFS_CLUSTER)
if [ -n "$NSS" ] && [ "$NSS" != UNAVAILABLE ]; then
  if [ "$NSS" = 4096 ]; then add PASS "NTFS 扇区/簇" "sector=$NSS cluster=$NSC（4K 原生对齐）"; else add WARN "NTFS 扇区/簇" "sector=$NSS cluster=$NSC（非 4K，vhdx 随机 IO 打折）"; fi
else add NOTE "NTFS 扇区/簇" "读不到（需管理员权限）"; fi
WSLV=$(timeout 20 "$WSL_EXE" --version 2>/dev/null | iconv -f UTF-16LE -t UTF-8 2>/dev/null | tr -d '\r' | head -1)
if [ -n "$WSLV" ]; then
  VNUM=$(echo "$WSLV" | grep -oE '2\.[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  if [ -n "$VNUM" ]; then
    MAJ=$(echo "$VNUM" | cut -d. -f2)
    if [ "$MAJ" -ge 2 ]; then add PASS "WSL 版本" "$WSLV（支持 --manage --set-sparse / --move）"; else add WARN "WSL 版本" "$WSLV（<2.2 无 --set-sparse）"; fi
  else add PASS "WSL 版本" "$WSLV"; fi
fi

# ---------------- D. 文件系统 / 资源 ----------------
sec "D. 文件系统与资源"
ROOTLINE=$(df -h / | tail -1)
RUSE=$(echo "$ROOTLINE" | awk '{print $5}' | tr -d '%')
RAVAIL=$(echo "$ROOTLINE" | awk '{print $4}')
if [ -n "$RUSE" ]; then
  if   [ "$RUSE" -ge 90 ]; then add FAIL "根文件系统用量" "${RUSE}%（可用 ${RAVAIL}）"
  elif [ "$RUSE" -ge 80 ]; then add WARN "根文件系统用量" "${RUSE}%（可用 ${RAVAIL}）"
  else add PASS "根文件系统用量" "${RUSE}%（可用 ${RAVAIL}）"
  fi
fi
IUSE=$(df -i / | tail -1 | awk '{print $5}' | tr -d '%')
if [ -n "$IUSE" ]; then
  if   [ "$IUSE" -ge 90 ]; then add FAIL "inode 使用率" "${IUSE}%"
  elif [ "$IUSE" -ge 80 ]; then add WARN "inode 使用率" "${IUSE}%"
  else add PASS "inode 使用率" "${IUSE}%"
  fi
fi
MEMAV=$(free -m | awk '/^Mem:/{print $7}')
if [ -n "$MEMAV" ]; then
  if   [ "$MEMAV" -lt 1500 ]; then add FAIL "内存可用" "${MEMAV}MB（<1.5G 危险线）"
  elif [ "$MEMAV" -lt 3000 ]; then add WARN "内存可用" "${MEMAV}MB（<3G 偏低）"
  else add PASS "内存可用" "${MEMAV}MB"
  fi
fi
SWAP=$(awk 'NR>1{printf "%s(%.1fG) ", $1, $3/1048576}' /proc/swaps 2>/dev/null)
if [ -n "$SWAP" ]; then add PASS "swap" "$SWAP"; else add WARN "swap" "未启用"; fi
SWUSED=$(free -m | awk '/^Swap:/{print $3}'); SWTOT=$(free -m | awk '/^Swap:/{print $2}')
if [ -n "$SWTOT" ] && [ "$SWTOT" -gt 0 ]; then
  SWPCT=$(( SWUSED * 100 / SWTOT ))
  if [ "$SWPCT" -gt 50 ]; then add WARN "swap 使用率" "${SWPCT}%（${SWUSED}/${SWTOT}MB）"; else add PASS "swap 使用率" "${SWPCT}%"; fi
fi

# ---------------- E. 关键服务 ----------------
sec "E. 关键服务"
SYS=$(systemctl is-system-running 2>&1)
if [ "$SYS" = running ]; then add PASS "systemd" "running"; else add WARN "systemd" "${SYS:-未知}"; fi
FAILED=$(systemctl --failed --no-legend --no-pager 2>/dev/null | grep -c . )
if [ "${FAILED:-0}" -gt 0 ]; then add WARN "失败的 systemd 单元" "${FAILED} 个"; else add PASS "失败的 systemd 单元" "0 个"; fi
GWPID=$(pgrep -f 'dist/index.js gateway' | head -1)
if [ -n "$GWPID" ]; then add PASS "OpenClaw 网关" "运行中 (pid $GWPID)"; else add FAIL "OpenClaw 网关" "未发现进程"; fi
if ss -ltn 2>/dev/null | grep -q ':18789'; then add PASS "网关端口 18789" "监听中"; else add FAIL "网关端口 18789" "未监听"; fi
CJOBS=$(timeout 40 openclaw cron list --json 2>/dev/null | python3 -c "import sys,json;print(len(json.load(sys.stdin).get('jobs',[])))" 2>/dev/null)
if [ -n "$CJOBS" ]; then add PASS "cron 任务数" "$CJOBS 个"; else add WARN "cron 任务数" "未取到"; fi
ALIST=$(timeout 40 openclaw automations list --all 2>/dev/null)
ATOT=$(echo "$ALIST" | tail -n +2 | grep -c .)
ADIS=$(echo "$ALIST" | grep -c "disabled")
if [ -n "$ATOT" ] && [ "${ATOT:-0}" -gt 0 ]; then
  add WARN "automations 任务" "共 $ATOT 个，其中 $ADIS 个 disabled（体检类多为关停）"
fi

# ---------------- F. 配置漂移 ----------------
sec "F. 配置漂移"
CONF=/etc/wsl.conf
if [ -f "$CONF" ]; then
  if grep -q 'systemd=true' "$CONF"; then add PASS "wsl.conf systemd" "systemd=true"; else add WARN "wsl.conf systemd" "未开 systemd=true"; fi
  if grep -q '^\[interop\]' "$CONF" && grep -q 'appendWindowsPath=true' "$CONF"; then
    add PASS "wsl.conf interop" "appendWindowsPath=true"
  else
    add WARN "wsl.conf interop" "缺 [interop]/appendWindowsPath —— Windows 路径未注入 PATH"
  fi
  if grep -q 'default=j' "$CONF"; then add PASS "默认用户" "j"; else add WARN "默认用户" "未显式设 j"; fi
else
  add WARN "wsl.conf" "文件不存在"
fi
if echo "$PATH" | grep -qi 'Windows'; then add PASS "PATH 注入" "Windows 路径已进 PATH"; else add WARN "PATH 注入" "PATH 里没有 Windows 目录（interop 未生效）"; fi

# ---------------- G. 备份与回滚 ----------------
sec "G. 备份与回滚"
for f in /mnt/x/wsl-backup/*.tar /mnt/e/wsl-backup/*.tar; do
  [ -f "$f" ] || continue
  SZ=$(du -m "$f" 2>/dev/null | cut -f1)
  MAGIC=$(head -c 2 "$f" | od -An -tx1 | tr -d ' \n')
  USTAR=$(dd if="$f" bs=1 skip=257 count=5 2>/dev/null)
  LIST=$(head -c 4096 "$f" 2>/dev/null | tar -tf - 2>/dev/null | head -3 | tr '\n' ' ')
  if [ "$MAGIC" = "1f8b" ] || [ "$USTAR" = "ustar" ] || [ -n "$LIST" ]; then
    add PASS "整机导出镜像" "$f  ${SZ}M（magic=$MAGIC/ustar=${USTAR:-无}，首项：${LIST:-读不到}）"
  else
    add FAIL "整机导出镜像" "$f  ${SZ}M（表头异常 magic=$MAGIC）"
  fi
done
if [ -f /mnt/e/wsl-backup/pre-migration-20261022.tar.gz ]; then add PASS "迁移前快照" "E:/wsl-backup/pre-migration-20261022.tar.gz"; else add NOTE "迁移前快照" "E 盘未见 pre-migration 快照"; fi
LATEST=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
  BAGE=$(( ( $(date +%s) - $(stat -c %Y "$LATEST") ) / 3600 ))
  BSZ=$(du -m "$LATEST" 2>/dev/null | cut -f1)
  if   [ "$BAGE" -gt 50 ]; then add FAIL "每日工作区备份" "$(basename "$LATEST")  ${BSZ}M  已 ${BAGE}h 未更新（>50h）"
  elif [ "$BAGE" -gt 30 ]; then add WARN "每日工作区备份" "$(basename "$LATEST")  ${BSZ}M  已 ${BAGE}h 未更新（>30h）"
  else add PASS "每日工作区备份" "$(basename "$LATEST")  ${BSZ}M  ${BAGE}h 前"; fi
else
  add FAIL "每日工作区备份" "D:/openclaw-backups 下没有备份包"
fi
# 整机 tar 异地副本核对（同名同大小）
OFFSITE_MISSING=0
for t in /mnt/x/wsl-backup/*.tar; do
  [ -f "$t" ] || continue
  B=$(basename "$t"); SZ=$(stat -c%s "$t" 2>/dev/null); FOUND=""
  for cand in "/mnt/e/wsl-backup/$B" "/mnt/h/wsl-backup/$B" "/mnt/d/wsl-backup/$B"; do
    if [ -f "$cand" ] && [ "$(stat -c%s "$cand" 2>/dev/null)" = "$SZ" ]; then FOUND="$cand"; break; fi
  done
  if [ -n "$FOUND" ]; then
    add PASS "整机 tar 异地副本" "$B —— $FOUND 同名同大小（$((SZ/1024/1024))M）"
  else
    OFFSITE_MISSING=1
    add FAIL "整机 tar 异地副本" "$B 在 E/H/D 上无同名同大小副本（X 故障则回滚材料同没）"
  fi
done
if [ "$(kv OLD_DIR_ITEMS)" != "0" ] && kva OLD_ITEM | grep -qi 'ext4.vhdx'; then
  add WARN "旧位置残留" "D:\\WSL\\Ubuntu 里还有 ext4.vhdx（占空间，需人工确认）"
else
  add PASS "旧位置残留" "D:\\WSL\\Ubuntu 已清空（只剩 shortcut.ico）"
fi
if [ "$DEEP" = 1 ]; then
  OTHERS=$(kva OTHER_VHDX)
  if [ -n "$OTHERS" ]; then
    add NOTE "全盘 vhdx 副本" "$(echo "$OTHERS" | tr '\n' ' ')"
  else
    add PASS "全盘 vhdx 副本" "只此一份（无异地回滚盘）"
  fi
fi

# ---------------- H. 风险提示 ----------------
sec "H. 风险与提醒"
add NOTE "夜间断网窗口" "每晚 04:00–06:00 路由器重启断网，勿排重 IO/联网任务"
add NOTE "每日全量备份" "01:00 起，其它重任务排 02:00 后"
if [ "$VSP" = 0 ]; then
  add WARN "vhdx 不自动回收" "非稀疏 → 删了文件盘位也不缩；需 wsl --shutdown 后 compact（要停机窗口）"
fi
if [ "${OFFSITE_MISSING:-0}" = 1 ] && [ -f "$VFILE" ]; then
  add WARN "回滚单点" "整机 tar 与 vhdx 同在 X 盘且无异地副本 —— X 故障则两者同没"
fi
add NOTE "休眠/睡眠" "Windows 睡眠前建议 wsl --shutdown，否则 vhdx 有损坏风险"
if [ "${ADIS:-0}" -gt 0 ] && [ "${ATOT:-0}" -gt 0 ]; then
  add WARN "体检任务停用" "automations 里 $ADIS/$ATOT 个任务是 disabled（含每日自检/进程体检/EH 盘体检）"
fi

# ---------------- 汇总 ----------------
if [ "$MODE" = human ]; then
  printf '\n\033[1m【汇总】\033[0m 通过 %d · 警告 %d · 失败 %d · 提示 %d\n' "$PASS" "$WARN" "$FAIL" "$NOTE"
  if [ "$WARN" -gt 0 ] || [ "$FAIL" -gt 0 ]; then
    echo "  结论：⚠️ 有待处理项（见上）；本脚本只报告不自动修"
  else
    echo "  结论：✅ 全部通过"
  fi
elif [ "$MODE" = quiet ]; then
  echo "WSL盘位体检：通过 $PASS · 警告 $WARN · 失败 $FAIL · 提示 $NOTE"
else
  python3 - "$ENT" "$PASS" "$WARN" "$FAIL" "$NOTE" <<'PY'
import json,sys,datetime
ent,pa,wa,fa,no=sys.argv[1:6]
items=[]
for line in open(ent,encoding='utf-8'):
    line=line.rstrip('\n')
    if not line: continue
    lvl,item,det=line.split('\t',2)
    items.append({"level":lvl,"item":item,"detail":det})
print(json.dumps({
 "tool":"wsl-disk-health","ts":datetime.datetime.now().isoformat(timespec='seconds'),
 "summary":{"pass":int(pa),"warn":int(wa),"fail":int(fa),"note":int(no),
            "exit_code":2 if int(fa)>0 else (1 if int(wa)>0 else 0)},
 "items":items},ensure_ascii=False,indent=2))
PY
fi

if [ "$FAIL" -gt 0 ]; then exit 2; fi
if [ "$WARN" -gt 0 ]; then exit 1; fi
exit 0
