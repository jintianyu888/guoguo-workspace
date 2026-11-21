#!/usr/bin/env bash
# journald-4g.sh —— 把 systemd journal 上限提到 4G、保留 14 天（需 root）
# 用途：2026-11-21 事故后，日志只有 1.3G 且被判损坏重建，14:24 前证据全丢。
# 运行：sudo bash /home/j/.openclaw/workspace/tools/journald-4g.sh
set -eu
DROPIN=/etc/systemd/journald.conf.d/50-oc-size.conf
mkdir -p /etc/systemd/journald.conf.d
cat > "$DROPIN" <<'EOF'
# 由 tools/journald-4g.sh 写入 2026-11-21
[Journal]
SystemMaxUse=4G
SystemKeepFree=8G
SystemMaxFileSize=256M
MaxRetentionSec=14day
EOF
echo "[*] 已写入 $DROPIN"
cat "$DROPIN"
systemctl restart systemd-journald
sleep 1
systemctl is-active systemd-journald
journalctl --disk-usage
echo "[*] 完成：上限 4G / 保留 14 天"
