#!/usr/bin/env python3
"""MusicGen 文本→音乐 CLI（本地 GPU，零 token）。

升级版 v2.1 — 支持风格预设、旋律参考、多段拼接、后期处理。
适配独立 venv：librosa 装在 demucs venv，melody 模式用 soundfile+torchaudio 替代。

用法:
  # 基础：文本生成
  python tools/musicgen.py --prompt "抒情钢琴" --seconds 30 --out x.wav

  # 预设风格
  python tools/musicgen.py --preset lyric --seconds 30 --out x.wav

  # 旋律参考（MusicGen Melody）
  python tools/musicgen.py --prompt "电子节奏" --ref ref.wav --seconds 20 --out x.wav

  # 多段结构 A-B-A
  python tools/musicgen.py --sections "intro:10,verse:20,chorus:20,verse:20,outro:10" \\
    --prompt "流行抒情" --out song.wav

  # 指定模型
  python tools/musicgen.py --prompt "..." --model large --out x.wav
"""
import argparse, os, sys, time, json, subprocess, tempfile, wave
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import torch
import torchaudio
import numpy as np
import soundfile as sf
from transformers import AutoProcessor, MusicgenForConditionalGeneration

# ─── 风格预设 ───────────────────────────────────────────────
PRESETS = {
    "lyric":    {"prompt": "emotional lyrical piano with soft strings, gentle melody, warm reverb, cinematic", "guidance": 3.0, "temp": 1.0},
    "electronic": {"prompt": "upbeat electronic dance music, synth bass, four-on-the-floor kick, energetic", "guidance": 3.5, "temp": 1.1},
    "chinese":  {"prompt": "Chinese traditional music, guzheng and erhu, pentatonic melody, serene and elegant", "guidance": 3.0, "temp": 0.9},
    "upbeat":   {"prompt": "cheerful upbeat pop, bright guitars, catchy melody, sunny and feel-good", "guidance": 3.5, "temp": 1.1},
    "tense":    {"prompt": "dark tense cinematic tension, low drones, ominous strings, suspenseful thriller", "guidance": 4.0, "temp": 0.8},
    "ambient":  {"prompt": "ambient atmospheric soundscape, ethereal pads, slowly evolving textures, meditation", "guidance": 2.5, "temp": 0.9},
    "rock":     {"prompt": "energetic rock, distorted electric guitars, driving drums, powerful bass, anthemic", "guidance": 3.5, "temp": 1.2},
    "lofi":     {"prompt": "lo-fi hip hop, jazzy chords, vinyl crackle, mellow boom bap beat, chill and relaxed", "guidance": 3.0, "temp": 1.0},
    "orchestral": {"prompt": "epic orchestral, full symphony, soaring strings, brass crescendo, heroic cinematic", "guidance": 3.5, "temp": 1.0},
    "acoustic": {"prompt": "warm acoustic guitar fingerpicking, soft percussion, intimate and cozy, folk", "guidance": 3.0, "temp": 1.0},
}

# ─── 模型选择 ──────────────────────────────────────────────
MODELS = {
    "small":   "facebook/musicgen-small",
    "medium":  "facebook/musicgen-medium",
    "large":   "facebook/musicgen-large",
    "melody":  "facebook/musicgen-melody",
}

# ─── venv 路径 ─────────────────────────────────────────────
DEMUCS_VENV = "/home/j/.openclaw/venvs/demucs"

def load_model(name, fp16=True):
    """加载模型，3070 上用 fp16 省显存。"""
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if (fp16 and dev == "cuda") else torch.float32
    proc = AutoProcessor.from_pretrained(name)
    model = MusicgenForConditionalGeneration.from_pretrained(
        name, torch_dtype=dtype
    ).to(dev)
    model.eval()
    return proc, model, dev

def load_audio_resampled(path, target_sr=32000):
    """用 torchaudio 加载音频并重采样到目标采样率。
    替代 librosa.load，避免对 librosa 的依赖。"""
    waveform, sr = torchaudio.load(path)
    # 单声道
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    # 重采样
    if sr != target_sr:
        resampler = torchaudio.transforms.Resample(sr, target_sr)
        waveform = resampler(waveform)
    return waveform.squeeze(0).numpy()

def generate_segment(proc, model, dev, prompt, seconds, ref_wav=None,
                     guidance=3.0, temp=1.0, top_k=250, seed=7):
    """生成一段音频。如果提供 ref_wav，用旋律参考模式。"""
    torch.manual_seed(seed)
    max_tokens = int(seconds * 50)  # MusicGen 每秒 ~50 tokens

    if ref_wav:
        # 旋律参考模式：用 torchaudio 加载参考音频
        y = load_audio_resampled(ref_wav, target_sr=32000)
        inputs = proc(text=[prompt], audio=[y], sampling_rate=32000,
                      padding=True, return_tensors="pt").to(dev)
    else:
        inputs = proc(text=[prompt], padding=True, return_tensors="pt").to(dev)

    with torch.no_grad():
        audio = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=True,
            guidance_scale=guidance,
            temperature=temp,
            top_k=top_k,
        )
    sr = model.config.audio_encoder.sampling_rate
    data = audio[0, 0].cpu().float().numpy()
    # 归一化到 [-1, 1]
    peak = np.max(np.abs(data))
    if peak > 0:
        data = data / peak * 0.95
    return data, sr

def apply_postprocess(data, sr, fade_in=1.0, fade_out=2.0, target_lufs=-16.0):
    """后期处理：淡入淡出 + 响度归一化。"""
    if fade_in > 0:
        fi = int(fade_in * sr)
        fi = min(fi, len(data))
        data[:fi] *= np.linspace(0, 1, fi)
    if fade_out > 0:
        fo = int(fade_out * sr)
        fo = min(fo, len(data))
        data[-fo:] *= np.linspace(1, 0, fo)

    # 简单响度归一化（RMS → target LUFS 近似）
    rms = np.sqrt(np.mean(data**2) + 1e-8)
    target_rms = 10 ** (target_lufs / 20) * 0.5  # 近似
    if rms > 0:
        data = data * (target_rms / rms)
        peak = np.max(np.abs(data))
        if peak > 0.98:
            data = data / peak * 0.98
    return data

def concat_segments(segments):
    """拼接多段音频，带交叉淡化。"""
    if len(segments) == 1:
        return segments[0]
    result = segments[0]
    for seg in segments[1:]:
        # 0.3s 交叉淡化
        xfade = int(0.3 * 32000)
        if len(result) > xfade and len(seg) > xfade:
            result[-xfade:] = result[-xfade:] * np.linspace(1, 0, xfade) + \
                              seg[:xfade] * np.linspace(0, 1, xfade)
            result = np.concatenate([result, seg[xfade:]])
        else:
            result = np.concatenate([result, seg])
    return result

def save_wav(data, sr, out_path, stereo=True):
    """保存 WAV，可选立体声。"""
    data = data.astype(np.float32)
    if stereo:
        # 简单立体声化：微延迟模拟宽度
        if len(data.shape) == 1:
            delay = int(0.015 * sr)  # 15ms Hass 效应
            right = np.concatenate([np.zeros(delay), data[:-delay]])
            data = np.stack([data, right], axis=-1)
    sf.write(out_path, data, sr, subtype='FLOAT')

def main():
    ap = argparse.ArgumentParser(description="MusicGen v2.1 — 文本→音乐（本地 GPU）")
    ap.add_argument("--prompt", help="文本提示词")
    ap.add_argument("--preset", choices=list(PRESETS.keys()), help="风格预设（覆盖 prompt）")
    ap.add_argument("--seconds", type=float, default=10.0, help="时长（秒）")
    ap.add_argument("--out", required=True, help="输出 WAV 路径")
    ap.add_argument("--model", choices=list(MODELS.keys()), default="medium",
                    help="模型档位（small/medium/large/melody）")
    ap.add_argument("--ref", help="旋律参考音频路径（需 melody 模型）")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--guidance", type=float, default=None, help="引导强度（覆盖预设）")
    ap.add_argument("--temp", type=float, default=None, help="温度（覆盖预设）")
    ap.add_argument("--sections", help="多段结构，如 'intro:10,verse:20,chorus:20,outro:10'")
    ap.add_argument("--no-fp16", action="store_true", help="禁用 fp16")
    ap.add_argument("--no-post", action="store_true", help="禁用后期处理")
    ap.add_argument("--mono", action="store_true", help="单声道输出")
    args = ap.parse_args()

    # 确定提示词和参数
    if args.preset:
        p = PRESETS[args.preset]
        prompt = args.prompt or p["prompt"]
        guidance = args.guidance or p["guidance"]
        temp = args.temp or p["temp"]
    else:
        if not args.prompt:
            ap.error("需要 --prompt 或 --preset")
        prompt = args.prompt
        guidance = args.guidance or 3.0
        temp = args.temp or 1.0

    model_name = MODELS[args.model]
    if args.ref and args.model != "melody":
        print(f"[warn] 旋律参考需要 melody 模型，自动切换", flush=True)
        model_name = MODELS["melody"]

    print(f"[config] model={model_name} prompt={prompt!r} sec={args.seconds} "
          f"guidance={guidance} temp={temp}", flush=True)

    # 加载模型
    t0 = time.time()
    proc, model, dev = load_model(model_name, fp16=not args.no_fp16)
    print(f"[load] {time.time()-t0:.1f}s on {dev} "
          f"({'fp16' if not args.no_fp16 else 'fp32'})", flush=True)

    # 解析多段
    if args.sections:
        sections = []
        for part in args.sections.split(","):
            name, dur = part.strip().split(":")
            sections.append((name.strip(), float(dur)))
        print(f"[sections] {' + '.join(f'{n}:{d}s' for n,d in sections)}", flush=True)

        all_segs = []
        for i, (name, dur) in enumerate(sections):
            t1 = time.time()
            seg_data, sr = generate_segment(
                proc, model, dev, prompt, dur, args.ref,
                guidance, temp, seed=args.seed + i
            )
            print(f"[gen] {name}: {dur}s → {len(seg_data)/sr:.2f}s in {time.time()-t1:.1f}s", flush=True)
            all_segs.append(seg_data)

        # 拼接
        data = concat_segments(all_segs)
    else:
        t1 = time.time()
        data, sr = generate_segment(
            proc, model, dev, prompt, args.seconds, args.ref,
            guidance, temp, seed=args.seed
        )
        print(f"[gen] {args.seconds}s → {len(data)/sr:.2f}s in {time.time()-t1:.1f}s", flush=True)

    # 后期处理
    if not args.no_post:
        data = apply_postprocess(data, sr, fade_in=1.0, fade_out=2.0)

    # 保存
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    save_wav(data, sr, args.out, stereo=not args.mono)
    print(f"[ok] {args.out} sr={sr} dur={len(data)/sr:.2f}s "
          f"stereo={'yes' if not args.mono else 'no'}", flush=True)

    # 释放显存
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

if __name__ == "__main__":
    main()
