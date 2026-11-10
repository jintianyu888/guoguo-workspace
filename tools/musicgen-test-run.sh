#!/bin/bash
mkdir -p /home/j/.openclaw/workspace/state/tmp/musicgen-test
cd /home/j/.openclaw/workspace
/home/j/.openclaw/venvs/tts312/bin/python tools/musicgen.py --preset lyric --seconds 10 --out /home/j/.openclaw/workspace/state/tmp/musicgen-test/test_lyric.wav
echo "EXIT=$?"
ls -la /home/j/.openclaw/workspace/state/tmp/musicgen-test/
