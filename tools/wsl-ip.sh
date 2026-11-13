#!/usr/bin/env bash
# 打印 WSL eth0 的 IPv4，用于 Windows 侧刷新 portproxy
ip -4 addr show eth0 2>/dev/null | awk '/inet /{sub(/\/.*/,"",$2); print $2; exit}'
