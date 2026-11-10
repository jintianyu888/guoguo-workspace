#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分级闸 tools/tier-gate.py —— 动手前先判档：P0/L3/L2/L1/L0
用法:
  tier-gate.py --action "改 cron 的备份参数" --tags cron,backup
  tier-gate.py --list-tags
判定以 --tags 为准（结构化）；关键词只给"疑似"提示，不作为定档依据。
"""
import sys, argparse

# tag -> (档位, 理由)
TAGS = {
    "restart":    ("P0", "重启/关机"),
    "shutdown":   ("P0", "关机"),
    "resource":   ("P0", "资源上限/内存/CPU 配额"),
    "permission": ("P0", "权限扩容/白名单"),
    "secret":     ("P0", "密钥录入"),
    "firewall":   ("P0", "防火墙/端口暴露"),
    "systemd":    ("P0", "systemd/计划任务结构变更"),
    "bulkdelete": ("P0", "批量删除"),
    "upgrade":    ("P0", "版本升级"),
    "manual":     ("P0", "需人工操作 GUI/BIOS/采购/口令"),

    "delete":     ("L3", "删除类（含单条）"),
    "credential": ("L3", "凭据迁移/轮换/外发"),
    "external":   ("L3", "对外发送"),
    "spend":      ("L3", "花钱"),
    "retention":  ("L3", "备份保留策略/备份链"),

    "script":     ("L2", "改脚本"),
    "process":    ("L2", "改流程"),
    "config":     ("L2", "改配置（非网关/systemd/权限）"),
    "cron":       ("L2", "cron 增改"),
    "report":     ("L2", "报告/看板格式"),
    "data":       ("L2", "自有数据整理"),
    "heavyio":    ("L2", "大范围遍历/重 IO（可拖死网关）"),

    "readonly":   ("L1", "只读诊断/查询/日志"),
    "draft":      ("L1", "自建区文档/脚本草稿"),
    "rollback1":  ("L1", "可一键回滚的小改动"),

    "query":      ("L0", "单条查询/看状态"),
}
ORDER = {"P0": 0, "L3": 1, "L2": 2, "L1": 3, "L0": 4}
REVIEW = {"P0": "0 审 —— 报主公等答复，不擅动",
          "L3": "3 审并行（3 家不同厂商，任一否决即停）",
          "L2": "2 审（不一致加第三审，3 取 2）",
          "L1": "自审 —— 自己核证据 + 写回滚点，事后报备",
          "L0": "免审免报"}
EVIDENCE = {"P0": "选项 + 代价 + 回滚命令",
            "L3": "文件:行号:原文 + 回滚命令 + 台账一行",
            "L2": "文件:行号:原文 + 回滚点",
            "L1": "证据片段 + 回滚点",
            "L0": "无"}

# 关键词只做"疑似"提示
HINTS = [
    (["重启", "restart", "reboot"], "restart"),
    (["关机", "shutdown", "poweroff"], "shutdown"),
    (["删除", "删掉", "清理", "rm "], "delete"),
    (["密钥", "key", "token", "口令", "secret"], "credential"),
    (["权限", "白名单", "allowlist"], "permission"),
    (["cron", "定时", "计划任务"], "cron"),
    (["扫描", "遍历", "全盘", "walk"], "heavyio"),
    (["备份", "保留", "retention"], "retention"),
    (["发到", "发给", "外发", "邮件"], "external"),
]

def classify(action, tags):
    if tags:
        tiers = [TAGS[t][0] for t in tags if t in TAGS]
        unknown = [t for t in tags if t not in TAGS]
    else:
        tiers, unknown = [], []
    if not tiers:
        tiers = ["L1"]  # 无标记默认按 L1，交人工确认
    best = sorted(tiers, key=lambda x: ORDER[x])[0]
    return best, unknown

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", default="")
    ap.add_argument("--tags", default="")
    ap.add_argument("--list-tags", action="store_true")
    a = ap.parse_args()
    if a.list_tags:
        for t, (tier, why) in sorted(TAGS.items(), key=lambda kv: ORDER[kv[1][0]]):
            print(f"{tier:3s} {t:12s} {why}")
        return 0
    tags = [x.strip() for x in a.tags.split(",") if x.strip()]
    tier, unknown = classify(a.action, tags)
    print(f"档位: {tier}")
    print(f"审级: {REVIEW[tier]}")
    print(f"证据: {EVIDENCE[tier]}")
    hits = sorted({TAGS[t][0] for kw, t in HINTS if any(k.lower() in a.action.lower() for k in kw)}, key=lambda x: ORDER[x])
    if hits and ORDER[hits[0]] < ORDER[tier]:
        print(f"⚠️ 疑似更高档: {hits[0]}（描述命中关键词，需人工确认是否升档）")
    if unknown:
        print(f"⚠️ 未知 tag（已忽略，请人工判档）: {unknown}")
    if not tags:
        print("⚠️ 未给 --tags，按默认 L1 处理；请补标签以免误判")
    return 0

if __name__ == "__main__":
    sys.exit(main())
