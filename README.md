# 爆款影片复刻 · Viral Video Replica

用 Claude 1:1 复刻爆款影片：拆片 → 用代码画每一帧 → 合成声音 → 量化相似度。
每条复刻一个文件夹，画面和声音全部由代码生成，不用素材。

| # | 作品 | 原片 | 画面相似度 | 声音相似度 | 文件夹 |
| --- | --- | --- | --- | --- | --- |
| 01 | 《权力意志》哲学概念片（87 秒） | 抖音 @叁号暗房 | SSIM 74% | 响度曲线 88% | [01-quanliyizhi](./01-quanliyizhi) |

## 通用环境
```bash
npm i -g playwright && npx playwright install chromium
pip install numpy scipy
# 另需 FFmpeg；中文字体用思源宋体 Noto Serif CJK SC
```
进入某一条的文件夹，运行 `./build.sh` 即可出片，详见各自的 README。

## 声明
所有原片版权归原作者所有，本仓库仅供学习复刻。发布自己的作品时，请换成自己的文案、品牌和出处。
