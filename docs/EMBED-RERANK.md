# 本地 Embedding + Rerank（中文）

落地日期：2026-09-28 · 全部用户级，无 root · 零 token / 零 API 调用

## 一句话总结

在本机 WSL 用 **fastembed + onnxruntime（ONNX，CPU）** 跑通了中文向量化与重排序，
两个 CLI：`tools/embed`（向量/相似度）与 `tools/rerank`（相关度排序）。
模型在本地 `tools/models/`，不联网、不调 API、不烧 token。

## 装了什么

| 组件 | 位置 | 说明 |
|---|---|---|
| venv | `tools/embed-venv` | Python 3.14.4（`--without-pip` 创建，pip 手动引导） |
| fastembed | 0.8.1 | 引擎，自带 tokenizer + ONNX 推理，**不依赖 torch/transformers** |
| onnxruntime(-gpu) | 1.30.0 | 推理后端（**已装 GPU 版**；providers：**CUDA / TensorRT / CPU**）· 2026-09-29 补齐 CUDA 13 运行库后可用 ✅ |
| tokenizers | 0.23.2 | 分词 |
| huggingface_hub | 1.33.0 | 模型下载 |
| 其它 | numpy 2.5.3 等 | 无 torch、无 CUDA 依赖 |

体积小：整个 venv 不含 torch/CUDA，远小于 torch 方案。

## 模型在哪

| 模型 | 用途 | 位置 | 体积 |
|---|---|---|---|
| BAAI/bge-small-zh-v1.5 | 向量化（512 维） | `tools/models/models--Qdrant--bge-small-zh-v1.5` | ~91 MB |
| BAAI/bge-reranker-base | 重排序（cross-encoder） | `tools/models/models--BAAI--bge-reranker-base` | ~1.1 GB（onnx/model.onnx 1.04G + tokenizer 17M） |

## 怎么用

```bash
# 1) 向量化（每个句子一个 512 维向量）
tools/embed "今天天气不错" "明天可能下雨"
tools/embed --file 句子.txt          # 每行一个句子
echo "一句话" | tools/embed --stdin  # 从标准输入逐行读
tools/embed --raw "一句话"           # 只输出纯向量数组

# 2) 相似度（余弦，自动降序）
tools/embed --query "怎么减肥最有效" --docs "坚持跑步和控制饮食" "明天开会" "股票大涨"

# 3) 重排序（cross-encoder 打分，自动降序）
tools/rerank "北京有什么好玩的" "故宫是必去景点" "今天下雨了" "我喜欢吃饺子"
tools/rerank "如何做好红烧肉" --file 候选.txt
tools/rerank "..." "a" "b" "c" --top 5   # 只输出前 5

# 4) 尝试 GPU（本机自动回退 CPU，见下）
tools/embed --gpu "句子"
tools/rerank --gpu "查询" "候选1" "候选2"
```

输出为 JSON（UTF-8，可直接用 jq / python 解析）。
两个 CLI 都是可执行 Python 脚本，shebang 指向 venv 的 python，`chmod +x` 已设。

## GPU 开关

- **已装 GPU 版** ✅（2026-09-29 晚更新）：`onnxruntime-gpu 1.30.0` 已装，可用执行器含 **`CUDAExecutionProvider`** / `TensorrtExecutionProvider`（实测 ✅）。`--gpu` 优先走 GPU，不可用自动回落 CPU ✅
- GPU 是 RTX 3070 8GB（nvidia-smi 可见，空闲 ~7.4G），但 **onnxruntime 走 GPU 需要
  `onnxruntime-gpu` + CUDA toolkit + cuDNN**，这些本机**未安装**（要 root/apt，体积大）。
- 因此 `--gpu` 只是「尝试」，本机会打出
  `CUDA 不可用，已回退 CPU：Provider CUDAExecutionProvider is not available`
  然后照常用 CPU 跑，**不影响结果**。
- 若以后要开 GPU：装 `onnxruntime-gpu` + 系统 CUDA/cuDNN（需 root），或在
  `tools/embed-venv` 里把 `onnxruntime` 换成 `onnxruntime-gpu` 并把 provider 改成
  CUDAExecutionProvider。**不建议**——CPU 已经够快，且避免依赖膨胀。

## 实测数据（CPU，2026-09-28）

三组中文句子的相似度/排序结果：

```
组1  embed  "怎么减肥最有效"
     → 坚持跑步和控制饮食 0.6211  ★
     → 股票今天大涨       0.2606
     → 明天要开会讨论预算 0.2457

组2  embed  "周末去哪里玩"
     → 可以去爬山或者去海边 0.4821  ★
     → 公司要发年终奖了     0.2483
     → 这道数学题很难       0.1664

组3  rerank "如何做好吃的红烧肉"
     → 红烧肉要小火慢炖才入味  3.286  ★
     → Python 编程入门教程   -10.19
     → 今天快递到了          -10.20
```

耗时（CPU）：

| 操作 | 耗时 |
|---|---|
| embed 加载模型 | ~0.7–1.3 s |
| embed 单句 | ~5–28 ms |
| embed 批量 50 句 | 0.12 s（~417 句/s） |
| rerank 加载模型 | ~9.8–11.9 s（1.04G ONNX 首次载入） |
| rerank 3 候选 | ~0.08 s |
| rerank 20 候选 | 0.17 s（~118 对/s） |

显存：**0 MB**（纯 CPU，不动 GPU）。CPU 内存：reranker 推理时约 +1~2 GB。

## 失败回退 CPU

- `--gpu` 已内置 try/except：CUDA 不可用自动回退 CPU，并打印原因，**不会崩**。
- 模型加载失败时，脚本会抛异常退出（非零码），不会静默给错结果。

## 坑（务必知道）

1. **系统 Python 3.14 没有 pip / ensurepip / python3-venv**（Debian 精简）。
   所以 venv 要用 `python3 -m venv --without-pip`，再手动引导 pip
   （从清华源下 pip/setuptools/wheel 的 wheel，解压进 site-packages）。
   别指望 `python3 -m pip`。
2. **外网（pypi.org / huggingface.co / bootstrap.pypa.io）又慢又容易断**；
   一律走国内镜像：
   - pip：`https://pypi.tuna.tsinghua.edu.cn/simple/`
   - HuggingFace：`HF_ENDPOINT=https://hf-mirror.com`（两个 CLI 已默认写好）
   - 下载用 `wget -4`，别用 curl（curl 在 WSL 里对 IPv6/外网 TLS 容易卡）。
3. **BAAI/bge-reranker-base 是 Xet 存储**，hf-mirror 直接下会报
   `401 Unauthorized ... cas-server.xethub.hf.co`（重排文件重建失败）。
   **解法：加 `HF_HUB_DISABLE_XET=1`**（两个 CLI 已默认写好），改走普通 LFS。
4. 大文件下载可用 `python3 tools/multi-dl.py <url> <out> 16`（多连接分段，已验证）。
   本次 reranker 的 1.04G ONNX 实际是靠 `HF_HUB_DISABLE_XET=1` 续传下来的；
   multi-dl.py 是兜底手段。
5. fastembed 里 `cuda` 和 `providers` **互斥**，只能传一个，别同时传。
6. reranker 模型 1.04G，首次加载 ~10s（读 ONNX 进内存）；embedding 模型很小，秒开。

## 维护

- venv 重建：见坑 1（`--without-pip` + 手动引导 pip）。
- 清缓存：模型在 `tools/models/`，删掉对应 `models--*` 目录即可重新下载
  （注意会触发重新下载，别误删）。默认**不删任何文件**。
- 新增模型：fastembed 支持列表见
  `tools/embed-venv/bin/python -c "from fastembed import TextEmbedding; print([m['model'] for m in TextEmbedding.list_supported_models()])"`。
