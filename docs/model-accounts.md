# 模型账号对照表（2026-09-27 主公定名）

## 正式名称（以此为准）

| 名称 | 档案 ID | 说明 |
|---|---|---|
| **百度千帆** | `qianfan` | **provider 正名**，不改叫别的 ✅ |
| **deepseek7折账户** | `deepseek:new` | **我们现在正在用的这个 API 的名字** ✅ |

## 当前路由（2026-09-27 09:16 起）

```
primary   : qianfan/deepseek-v4-pro        （百度千帆）
fallbacks : deepseek/deepseek-v4-pro@deepseek:new   （deepseek7折账户，排第一）
            qwen/qwen3.8-flash · qwen/qwen3.8-max · zai/glm-5.3
```

- **为什么切**：`deepseek7折账户` **余额将尽**，主公晚点充值 → 先走**百度千帆**顶着，**不断工** ✅
- **充值到账后**：把 primary 改回 `deepseek/deepseek-v4-pro@deepseek:new` 即可（它现在就在 fallback 第一位，也可临时用 `/model DeepSeek -s` 切）✅

## 其他 provider（2026-09-27 主公明令：已全部移除）

> 主公原话：「除了 deepseek 和本地大模型，别的模型都去掉」。以下 provider 已从 openclaw.json 删除，**不再是备用**；保留此表仅供查历史。

### 历史记录（已删除）

| 名称 | 档案 | 常用模型 |
|---|---|---|
| 通义千问 | `qwen` | `qwen3.8-max`(max) · `qwen3.8-flash`(fast) |
| 智谱 | `zai` | `glm-5.3`(smart) |
| 火山豆包 | `volcengine` | `doubao` |
| Kimi | `moonshot` | `kimi-k3`（1M 上下文）|
| 本地 | `ollama` | `local` · `local-30b`（不出内网）|
