# print-hires-pdf.py `--fit-up` 交叉评审记录（2026-10-23）

## 背景
- 故障：`place()` 的 `fill` 分支 `im2.resize((aw, ah))` 是**硬拉伸**，注释却写「等比放大铺满」。
- 后果 1：`--no-fill` 完全不放大 → 808px 在 600dpi A4 上仅 34mm 宽，打出来是邮票（#98/#100/#101 白费纸）。
- 后果 2：默认铺满对矮图（808×365）纵向拉伸约 3 倍，字变瘦高不可用（#100/#101 亦因此作废）。
- 结论：需新增 `--fit-up`（等比放大到页内最大，取宽比/高比小者），根治小图/矮图。

## 送审内容
- 现状 `place()` 代码 + 调用点（居中 paste）+ 三个已观测故障 + 拟改法（三 mode：fill/none/fit_up，默认保持 fill 以兼容 print-score.sh）。

## 评审结果（两路均 outcome=ok，正文完整，四点逐条回答 + 结论句）

### 1) deepseek/deepseek-v4-pro — 结论：**需修改**
- 必改①：源图 0 宽高未守卫，损坏图会落入 fit_up 分支 `aw/im2.width` → **ZeroDivisionError 崩整单**。需入口加 `if im2.width<=0 or im2.height<=0: return im2`。
- 必改②：resize 结果夹紧 `min(aw, max(1, round(...)))`，绝对稳妥。
- s==1 守卫正确；LANCZOS 放大质量可接受；mode 非法值校验为可选。
- **默认值**：保持 fill 合理 —— print-score.sh 头注释 2026-10-03 已把「铺满」定为乐谱默认，乐谱接近全页、拉伸幅度小。
- **警告**：不建议无条件 runtime warn（默认路径就是 fill，会污染日志）；改在 help/usage 文案标注。

### 2) zai/glm-5.3 — 结论：**同意**
- 零尺寸实际不可达（PIL 打不开 0 尺寸文件）；取整不会溢出画布，`min()` 钳位「非必需」；s==1 语义正确；LANCZOS 可用。
- **默认值**：建议**尽快翻成 fit_up** —— 原注释本就写「等比放大」，fill 属注释与实现不符的 bug；翻转只会改变「原本被拉歪」的输出，风险是改善。可先保 fill 兼容过渡，冒烟一页后翻转。
- **警告**：建议在 fill 分支且纵横比确实不匹配时（`|w/aw − h/ah| > 1e-6`）才向 stderr 提示，精确命中有害路径。

## 分歧与处理（按主公规矩：不选边，报主公）
1. **补丁是否可合并**：v4pro「需修改（加两处防护）」/ glm「同意，防护非必需」。→ 两处防护**彼此兼容且无副作用**，合并版同时吸收，故取交集不是选边。
2. **默认值 fill 还是 fit_up**：v4pro 保 fill / glm 主张翻 fit_up。→ **未决定，待主公拍板。**
3. **是否加告警**：v4pro 反对无条件 warn / glm 主张条件 warn。→ 建议采纳 glm 的「仅真拉伸时 warn」，倾向后者，仍待主公确认。

## 合并后的补丁（未落地，等主公批准）
```python
def place(im, W, H, margin_px, mode):
    # mode: 'fill'(旧默认,硬拉伸,兼容) | 'none'(不放大) | 'fit_up'(等比放大)
    aw, ah = max(1, W - 2 * margin_px), max(1, H - 2 * margin_px)
    im2 = im.copy()
    if im2.width <= 0 or im2.height <= 0:      # v4pro 必改①：防除零
        return im2
    if im2.width > aw or im2.height > ah:
        im2.thumbnail((aw, ah), Image.LANCZOS)
    elif mode == 'fill':
        im2 = im2.resize((aw, ah), Image.LANCZOS)
    elif mode == 'fit_up':
        s = min(aw / im2.width, ah / im2.height)
        if s > 1:
            nw = min(aw, max(1, round(im2.width * s)))    # 双方共识：夹紧
            nh = min(ah, max(1, round(im2.height * s)))
            im2 = im2.resize((nw, nh), Image.LANCZOS)
    return im2
```
CLI：`--fit-up` → mode='fit_up'；`--no-fill` → mode='none'；默认仍 `fill`。输出提示语分别标注「铺满(拉伸)/等比放大/不放大」。

## 落地前置条件
- 主公批准（脚本逻辑改动）。
- 落地后回归：`--dry` 跑 PDF + JPG 两条分支（**不出纸**，用户 22:05 已叫停打印）。