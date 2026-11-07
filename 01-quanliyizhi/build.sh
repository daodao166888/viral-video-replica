#!/usr/bin/env bash
# 一键出片：两路并行渲染画面 → 拼接 → 合成声音 → 混进视频
set -e
cd "$(dirname "$0")"
mkdir -p out
FRAMES=2609            # 86.97 秒 × 30fps
HALF=1305
node render.js 0 $HALF out/partA.mp4 &
node render.js $HALF $FRAMES out/partB.mp4 &
wait
printf "file 'partA.mp4'\nfile 'partB.mp4'\n" > out/list.txt
ffmpeg -v error -y -f concat -safe 0 -i out/list.txt -c copy out/silent.mp4
python3 sound.py
ffmpeg -v error -y -i out/silent.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy \
  -af "volume=3.4dB,alimiter=limit=0.85:attack=2:release=80:level=false" \
  -c:a aac -b:a 256k -shortest -movflags +faststart out/replica.mp4
echo "完成：out/replica.mp4"
