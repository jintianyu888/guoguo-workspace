# guoguo

主公机器的「代码 + 文档」备份仓（私有）。

## 里面有什么
- tools/   果果与五大管家的运维脚本（只收根目录脚本，不含 venv/模型/数据）
- docs/    规则、方案、复盘、手册
- panel/   果果助手（8899）前后端源码
- 根目录   AGENTS.md / SOUL.md / IDENTITY.md / USER.md / MEMORY.md

## 里面绝没有什么
密钥、.env、数据库、备份包、state/、data/、人脸库、NVR 抓拍、媒体文件。

## 同步方式
本机 `bash tools/github-sync.sh --local` 生成快照提交；`--push` 推送到 GitHub。
每日 23:20 由 `oc-github-sync.timer` 自动执行（无 token 时跳过）。
提交前会跑敏感串扫描，命中即中止。

## 恢复
换机后：clone 本仓 → 把 tools/ docs/ panel/ 放回原位 → 仍需另行恢复 state/ 与密钥（走备份链，不在本仓）。
