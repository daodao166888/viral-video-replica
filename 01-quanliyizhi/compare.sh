#!/usr/bin/env bash
# 量化复刻有多像：画面 SSIM（每秒 5 帧逐帧比）+ 并排对比图
# 用法：./compare.sh 原片.mp4 out/replica.mp4
set -e
ffmpeg -v error -i "$1" -i "$2" -filter_complex "[0:v]fps=5,scale=480:270,format=gray[a];[1:v]fps=5,scale=480:270,format=gray[b];[a][b]ssim=stats_file=ssim.txt" -f null -
python3 -c "import re,statistics as s;v=[float(re.search(r'All:([\d.]+)',l).group(1)) for l in open('ssim.txt')];print(f'画面 SSIM 平均 {s.mean(v):.3f}（{len(v)} 帧）')"
for t in 2 14 26 40 53 60 70 84; do
  ffmpeg -v error -ss $t -i "$1" -ss $t -i "$2" -frames:v 1 -filter_complex "[0:v]scale=640:-1[a];[1:v]scale=640:-1[b];[a][b]hstack" -y cmp_$t.png
done
echo "并排对比图：cmp_*.png（左原片 右复刻）"
