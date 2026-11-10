#!/bin/bash
# 核实：全量归档里到底有没有「回收站」
A=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
{
echo "归档: $(basename "$A") ($(du -h "$A" 2>/dev/null | cut -f1))"
echo "--- 是否含 workspace/回收站 ---"
timeout 900 tar tzf "$A" 2>/dev/null | grep -m 5 '回收站' 
echo "--- 抽样: 前 5 条 workspace 路径 ---"
timeout 900 tar tzf "$A" 2>/dev/null | grep -m 5 '/workspace/'
} > /home/j/.openclaw/workspace/state/archive-recycle-check.txt 2>&1
