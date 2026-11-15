#!/bin/bash
# audit-job-refresh.sh v2.0 — 迭代式互审（2026-11-15 主公语音令）
set -uo pipefail
W=/home/j/.openclaw/workspace; D=$(date +%F)
mk() { # id name peer_root peer own_root
  id=$1; name=$2; peer=$3; proot=$4; oroot=$5
  msg="你是${name}。今天按互审迭代流程做两件事，不要调用 exec/shell，只用 read 读文件，然后用回复正文输出。

第一件·写草稿：读你自己的事实包 ${oroot}/state/self-review/audit-inputs.md，写出今天的工作报告草稿，四段：做了什么的数字、没做到的、明日计划(带开始时间与用时)、风险与对策。直接在回复里输出全文，开头写【草稿】。

第二件·审对家：读 ${proot}/state/reports/draft.md（对家今天的草稿，可能不存在）。若存在，只挑硬伤，按三条给意见：①能否执行 ②漏洞在哪(具体到段落/数字) ③必须改哪几条。最后一行写『审定：${peer} 合格』或『审定：${peer} 不合格 ｜还需改：...』。若文件不存在，写『对家草稿未就绪，本轮不审』并结束。

禁止空话，禁止『基本合格』。"
  openclaw cron edit $id --message "$msg" >/dev/null 2>&1 && echo "updated $name"
}
mk aa6e71c3-fcf2-4119-9393-ad5ac4553889 维护管家 备份管家 /home/j/.openclaw/workspace-backup /home/j/openclaw-workspaces/maint
mk 123f03f2-2f3c-4987-ab86-00e5b83c8f64 备份管家 维护管家 /home/j/openclaw-workspaces/maint /home/j/.openclaw/workspace-backup
mk f2d7bf2f-2762-464c-87a2-74a22f765082 模型管家 干活管家 /home/j/openclaw-workspaces/work /home/j/.openclaw/workspace-model
mk 770cca92-b489-4326-8d9e-38ce9b3b0a6a 干活管家 模型管家 /home/j/.openclaw/workspace-model /home/j/openclaw-workspaces/work
mk 643ce055-43fc-4b06-8baa-deb53422f825 Hermess 果果 /home/j/.openclaw/workspace /home/j/openclaw-workspaces/sheet-music
