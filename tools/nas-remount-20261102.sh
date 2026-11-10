#!/bin/bash
# ⛔ 2026-11-02 22:30 作废：老 NAS（192.168.1.5）已退役，本脚本会把 fstab 指回老设备，禁止再运行。
#    新 NAS 走 //192.168.1.109/home -> /mnt/nas（见 tools/nas-config.sh）。
echo "⛔ 本脚本已作废（老 NAS 已退役），请勿运行；新 NAS 配置见 tools/nas-config.sh" >&2
exit 9
# OBSOLETE 2026-11-02：本脚本写的是「.104 → .5」，与现状不符（fstab 已指向 //192.168.1.109/home）。
# 保留仅作历史记录，已去掉执行位，勿运行。
# nas-remount-20261102.sh —— 群晖换址后重挂 /mnt/nas（需 sudo 执行，一次性）
# 背景：/mnt/nas 的 fstab 条目仍指向老地址 192.168.1.104（已下线），
#       群晖现址 192.168.1.5（SSH/445 已验证通，数据一致）。
# 安全：先备份 fstab，再改源地址，lazy umount 掉陈旧 CIFS，重挂并自检。
set -euo pipefail

echo "== 1. 备份 fstab =="
cp -a /etc/fstab "/etc/fstab.bak-nasmove-$(date +%Y%m%d%H%M%S)"
ls -l /etc/fstab.bak-nasmove-* | tail -2

echo "== 2. 改源地址 192.168.1.104 -> 192.168.1.5 =="
sed -i 's#^//192\.168\.1\.104/home#//192.168.1.5/home#' /etc/fstab
grep -n '/mnt/nas' /etc/fstab

echo "== 3. 卸掉陈旧挂载 =="
umount -l /mnt/nas 2>/dev/null || true
sleep 2
mountpoint -q /mnt/nas && { echo "仍在挂载，尝试强制卸载"; umount -f /mnt/nas || true; }

echo "== 4. 重挂 =="
mount /mnt/nas

echo "== 5. 验收 =="
df -h /mnt/nas | tail -1
echo "-- 目录抽样 --"
ls /mnt/nas | head -5
echo "OK remount-done"
