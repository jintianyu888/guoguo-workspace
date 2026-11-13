#!/usr/bin/env bash
# 用法: wb-eval.sh "<JS 表达式>"  → 通过 CDP 在 WorkBuddy 渲染进程里执行并打印结果
set -u
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
b64=$(printf "%s" "$1" | base64 -w0)
"$PS" -NoProfile -ExecutionPolicy Bypass -File "C:\openclaw\wb-cdp.ps1" "$b64" 2>&1 | tr -d "\r"
