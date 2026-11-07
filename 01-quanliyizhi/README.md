# 《权力意志》1:1 复刻 · 源码

用 Claude 从零复刻的哲学概念短片：87 秒，1920×1080，30fps，画面和声音全部由代码生成，没有用任何素材。
原片来自抖音 @叁号暗房，本仓库仅供学习复刻。

## 相似度
- 画面：SSIM 74%（每秒 5 帧，435 帧逐帧比对）
- 声音：每秒响度曲线相关度 88%，9 个倍频程能量差均在 ±1 dB 内
- 文案、字幕时间、场景顺序：100% 对齐

## 环境
```bash
npm i -g playwright && npx playwright install chromium
pip install numpy scipy
# 另需 FFmpeg；中文字体用思源宋体 Noto Serif CJK SC
```

## 用法
```bash
open replica.html                    # 浏览器预览：播放 / 拖动进度条逐帧看
node render.js still 2.5,40 s_%t.png  # 导出单帧
./build.sh                           # 一键出片 → out/replica.mp4
./compare.sh 原片.mp4 out/replica.mp4 # 算相似度 + 并排对比图
python3 analyze_audio.py orig.wav     # 从原片音轨重新提取鼓点 → drum_hits.json
```

## 文件
| 文件 | 作用 |
| --- | --- |
| replica.html | 全部画面，核心是 render(t) |
| render.js | Playwright 逐帧渲染 + FFmpeg 编码 |
| sound.py | 合成配乐与音效，输出 mix.wav |
| drum_hits.json | 从原片提取的 485 个鼓点 |
| analyze_audio.py | 生成鼓点表 |
| build.sh / compare.sh | 一键出片 / 量化对比 |

Windows 用户可在 Git Bash 或 WSL 里运行 .sh 脚本；若 Chrome 不在默认位置，设环境变量 CHROME_PATH。
