#!/bin/bash
# MusicGen v2 测试脚本 — 验证升级后的生成链路
# 用法: bash tools/test_musicgen.sh

set -e
PY=/home/j/.openclaw/venvs/tts312/bin/python
SCRIPT=tools/musicgen.py
OUT_DIR=/home/j/.openclaw/workspace/state/tmp/musicgen-test
mkdir -p "$OUT_DIR"

echo "═══════════════════════════════════════════"
echo "  MusicGen v2 测试 — $(date '+%Y-%m-%d %H:%M')"
echo "═══════════════════════════════════════════"

# 0. GPU 状态
echo ""
echo "── GPU ──"
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader 2>/dev/null || echo "(nvidia-smi 不可用)"

# 1. venv 包检查
echo ""
echo "── venv 包 ──"
$PY -c "import torch, transformers, soundfile, numpy; print(f'torch={torch.__version__} transformers={transformers.__version__} cuda={torch.cuda.is_available()} device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"cpu\"}')" 2>&1

# 2. 模型缓存检查
echo ""
echo "── HF 模型缓存 ──"
ls -1 ~/.cache/huggingface/hub/ 2>/dev/null | grep -i musicgen || echo "(无 musicgen 缓存)"

# 3. 生成测试 — 预设风格
echo ""
echo "── 测试1: 预设风格 (lyric, 10s) ──"
$PY $SCRIPT --preset lyric --seconds 10 --out "$OUT_DIR/test1_lyric.wav" 2>&1

# 4. 生成测试 — 自定义 prompt
echo ""
echo "── 测试2: 自定义 prompt (古风, 15s) ──"
$PY $SCRIPT --prompt "Chinese traditional guzheng music, serene pentatonic melody" --seconds 15 --out "$OUT_DIR/test2_chinese.wav" --model medium 2>&1

# 5. 生成测试 — 多段结构
echo ""
echo "── 测试3: 多段结构 A-B-A (30s) ──"
$PY $SCRIPT --preset ambient --sections "intro:8,main:15,outro:7" --out "$OUT_DIR/test3_sections.wav" 2>&1

# 6. 输出文件检查
echo ""
echo "── 输出文件 ──"
for f in "$OUT_DIR"/*.wav; do
    [ -f "$f" ] && echo "✓ $(basename $f): $(du -h "$f" | cut -f1)" || echo "✗ 缺失: $f"
done

echo ""
echo "═══════════════════════════════════════════"
echo "  测试完成 — 输出目录: $OUT_DIR"
echo "═══════════════════════════════════════════"
