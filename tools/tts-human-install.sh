#!/bin/sh
# tts-human-install.sh —— 后台装「更像人」的本地中文 TTS（ChatTTS + CosyVoice 依赖），装成即出样张
cd /home/j/.openclaw/workspace || exit 1
LOG=state/tts-human.log
echo "[$(date "+%F %T")] 开始" >> $LOG
# 1) ChatTTS（对话感强，中文自然）
echo "[$(date "+%F %T")] 装 ChatTTS" >> $LOG
timeout 1500 tools/asr-venv/bin/pip install --target tools/py-chattts -i https://pypi.tuna.tsinghua.edu.cn/simple ChatTTS >> $LOG 2>&1
ls tools/py-chattts 2>/dev/null | head -n 3 >> $LOG
# 2) 出样张（若装成）
if [ -d tools/py-chattts/chattts ] || [ -d tools/py-chattts/ChatTTS ]; then
  echo "[$(date "+%F %T")] 装成，出样张" >> $LOG
  HF_ENDPOINT=https://hf-mirror.com PYTHONPATH=tools/py-chattts timeout 900 tools/asr-venv/bin/python - >> $LOG 2>&1 <<PY
import torch, ChatTTS, soundfile as sf
torch.manual_seed(42)
chat = ChatTTS.Chat(); chat.load(compile=False)
wavs = chat.infer(["你好老板，我是果果。这是本地合成的语音，你看这条更像人吗？"])
sf.write("/home/j/.openclaw/workspace/state/tmp/tts-chattts.wav", wavs[0], 24000)
print("样张: /home/j/.openclaw/workspace/state/tmp/tts-chattts.wav")
PY
  echo "[$(date "+%F %T")] 样张完成" >> $LOG
else
  echo "[$(date "+%F %T")] ChatTTS 未装成" >> $LOG
fi
echo "[$(date "+%F %T")] 结束" >> $LOG