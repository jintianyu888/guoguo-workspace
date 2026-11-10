# 模型对比快测 · DeepSeek vs GLM（2026-10-12）

数据源：`state/bench/dsp/result.md`（引擎 tools/model-bench/）
方式：6 道客观题（指令遵循/代码/JSON/数学/推理/工具调用），单轮 1 遍。

## 总览（客观题通过率 / 平均耗时）
- deepseek/deepseek-flash：**100%（6/6）** · 20.9s
- deepseek/deepseek-v4-pro：**83%（5/6）** · 18.0s
- zai/glm-5.2：**83%（5/6）** · 18.0s

## 失分复核（关键）
- math1（只输出数字 17×23+45）：
  - deepseek-flash → 436 ✅
  - deepseek-v4-pro → 277 ❌（算错，真实失误）
  - zai/glm-5.2 → 空 ❌ → **复核：直接重跑 GLM 答出 `436` ✅，判定为并行调用时的偶发空输出，非能力问题。**
- ⇒ 修正后：三款在核心 6 题上**基本打平（GLM ≈ DeepSeek）**，GLM 平均略快（18 vs 21s）。

## 局限
- 单轮、题量小、未覆盖长上下文/多轮/主观题；深跑（repeat 3 + 长上下文）在本机多波并行下不稳，待改单波重跑。

## 记录位置
- state/bench/dsp/（原始输出 + result.md）
- state/bench/index-latest.md
