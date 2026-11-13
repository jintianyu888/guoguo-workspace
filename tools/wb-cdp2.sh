#!/usr/bin/env bash
# 用法: cat payload.json | wb-cdp2.sh   （payload = {"id":1,"method":"...","params":{...}}）
set -u
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
b64=$(base64 -w0)
"$PS" -NoProfile -ExecutionPolicy Bypass -File "C:\openclaw\wb-cdp2.ps1" "$b64" 2>&1 | tr -d "\r"
