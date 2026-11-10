#!/bin/bash
cd /home/j/.openclaw/workspace || { echo "b1-sha: 工作区不可达"; exit 1; }
F=state/work/b1-sha256.txt
{
echo "=== START $(date '+%F %T') ==="
echo "--- X ---"
sha256sum /mnt/x/wsl-backup/ubuntu-20261022.tar 2>&1
echo "--- E ---"
sha256sum /mnt/e/wsl-backup/ubuntu-20261022.tar 2>&1
echo "=== END $(date '+%F %T') ==="
} >> $F 2>&1

