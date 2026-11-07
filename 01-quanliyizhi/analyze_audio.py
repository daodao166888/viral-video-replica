"""
从原片音轨里提取鼓点时间表（drum_hits.json），供 sound.py 合成时逐个敲回去。
用法：
  ffmpeg -i 原片.mp4 -vn -ac 2 -ar 48000 orig.wav
  python3 analyze_audio.py orig.wav            → drum_hits.json
思路：
  1. 先用 hi-hat 的起音点拟合出速度和第一拍（本片：112.9 BPM，第一个八分音符在 0.115s）
  2. 在每个 16 分音符的位置，分别测底鼓(35–120Hz)、军鼓(1.5–5kHz)、hi-hat(7–16kHz)的“突然变响”程度
  3. 超过阈值的位置记成一次敲击，连同力度写进 JSON
"""
import sys, json
import numpy as np
import scipy.io.wavfile as wf
import scipy.signal as ss

src = sys.argv[1] if len(sys.argv) > 1 else 'orig.wav'
sr, x = wf.read(src); m = x.astype(np.float32).mean(1) / 32768
f, t, S = ss.stft(m, sr, nperseg=2048, noverlap=2048 - 240); A = np.abs(S)

def flux(lo, hi):  # 某个频段的“起音强度”曲线
    sel = (f >= lo) & (f < hi); L = np.log(A[sel] + 1e-5)
    return t[1:], np.maximum(0, np.diff(L, axis=1)).mean(0)

# 1) 用 hi-hat 起音点拟合速度与相位
tt, hf = flux(7000, 16000)
d = hf - ss.medfilt(hf, 41); pk, _ = ss.find_peaks(d, height=1.4 * d.std(), distance=int(.09 / (tt[1] - tt[0])))
hats = tt[pk]; best = (0, 0, 0)
for bpm in np.arange(100, 130, .02):
    P = 60 / bpm / 2
    for ph in np.linspace(0, P, 60, endpoint=False):
        e = ((hats - ph) / P + .5) % 1 - .5; sc = np.exp(-(e * P / .02) ** 2).sum()
        if sc > best[0]: best = (sc, bpm, ph)
_, BPM, T0 = best; P16 = 60 / BPM / 4
print(f'速度 {BPM:.1f} BPM，第一拍 {T0:.3f}s')

# 2) 每个 16 分音符位置的三类鼓的力度
_, kf = flux(35, 120); _, sf = flux(1500, 5000)
n = int((len(m) / sr - T0) / P16)
def slots(fl):
    v = np.zeros(n)
    for k in range(n):
        c = T0 + k * P16; sel = (tt >= c - .03) & (tt < c + .05); v[k] = fl[sel].max() if sel.any() else 0
    return v / np.percentile(v, 95)
K, Sn, Hh = slots(kf), slots(sf), slots(hf)

# 3) 写出时间表
hits = []
for k in range(n):
    c = round(T0 + k * P16, 4)
    if Hh[k] > .3: hits.append([c, 'hat', round(float(min(1.5, Hh[k])), 2)])
    if Sn[k] > .75: hits.append([c, 'snare', round(float(min(1.5, Sn[k])), 2)])
    if K[k] > .8: hits.append([c, 'kick', round(float(min(1.5, K[k])), 2)])
json.dump({'bpm': round(float(BPM), 2), 't0': round(float(T0), 4), 'hits': hits}, open('drum_hits.json', 'w'))
print(f'写出 drum_hits.json：{len(hits)} 个鼓点')
