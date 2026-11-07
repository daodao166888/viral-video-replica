"""
《权力意志》复刻 —— 用代码合成配乐与音效
原片分析：F 小调，约 112.5 BPM；低频 F1(≈44Hz) 持续铺底，按段落换和弦；
音效卡点与 replica.html 中的画面时间一一对应。
运行：python3 sound.py  → music.wav / sfx.wav / mix.wav
"""
import numpy as np
import scipy.io.wavfile as wf
import scipy.signal as ss

SR = 48000
DUR = 86.97
N = int(SR * DUR)
rng = np.random.default_rng(7)
import json, os
DRUMS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drum_hits.json')))
BEAT = 60 / DRUMS['bpm']          # 原片节拍：112.9 BPM
GRID0 = DRUMS['t0']                # 第一个八分音符的位置（秒）
snap = lambda t: GRID0 + np.ceil((t - GRID0) / (BEAT / 2)) * (BEAT / 2)

def note(n):  # 'F1' -> Hz
    names = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
    k, o = (n[:2], n[2:]) if n[:2] in names else (n[:1], n[1:])
    return 440 * 2 ** ((names[k] + 12 * (int(o) + 1) - 69) / 12)

def tvec(n): return np.arange(n) / SR
def bus(): return np.zeros((N, 2), np.float32)

def put(b, t0, sig, gain=1.0, pan=0.0):
    """把单声道或立体声信号放到总线上 t0 秒处"""
    i = int(t0 * SR)
    if i >= N: return
    if sig.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l * 1.414, sig * r * 1.414], 1)
    j = min(N, i + len(sig)); s0 = max(0, -i)
    b[max(i, 0):j] += (sig[s0:j - i] * gain).astype(np.float32)

def env_adsr(n, a, r, curve=2.0):
    e = np.ones(n); A = max(1, int(a * SR)); R = max(1, int(r * SR))
    e[:A] = np.linspace(0, 1, A) ** curve
    if R < n: e[-R:] *= np.linspace(1, 0, R) ** curve
    return e

def lp(x, fc, order=2): b, a = ss.butter(order, min(fc, SR / 2 * .95) / (SR / 2)); return ss.lfilter(b, a, x, axis=0)
def hp(x, fc, order=2): b, a = ss.butter(order, fc / (SR / 2), 'high'); return ss.lfilter(b, a, x, axis=0)
def bp(x, lo, hi, order=2): b, a = ss.butter(order, [lo / (SR / 2), min(hi, SR / 2 * .95) / (SR / 2)], 'band'); return ss.lfilter(b, a, x, axis=0)
def noise(n): return rng.standard_normal(n)

def sweep_bp(x, f0, f1, q=3.0, block=512):
    """带通中心频率随时间滑动的噪声（嗖声）"""
    out = np.zeros_like(x); n = len(x); zi = None
    for s in range(0, n, block):
        k = s / max(1, n - 1); fc = f0 * (f1 / f0) ** k
        lo, hi = fc / (1 + 1 / q), min(fc * (1 + 1 / q), SR / 2 * .9)
        b, a = ss.butter(2, [lo / (SR / 2), hi / (SR / 2)], 'band')
        if zi is None: zi = ss.lfilter_zi(b, a) * 0
        out[s:s + block], zi = ss.lfilter(b, a, x[s:s + block], zi=zi)
    return out

def reverb(x, decay=2.5, mix=.3, pre=.02, bright=6000):
    """合成混响：指数衰减的立体声噪声冲激响应"""
    n = int(decay * SR); t = tvec(n)
    c = noise(n); ir = np.stack([c * .75 + noise(n) * .45, c * .75 + noise(n) * .45], 1) * np.exp(-6.9 * t / decay)[:, None]
    ir = lp(ir, bright, 1); ir[:int(pre * SR)] = 0; ir /= np.sqrt((ir ** 2).sum(0))
    wet = np.stack([ss.fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], 1)
    return x * (1 - mix) + wet * mix * 2.2

# ============================================================
# 1. 配乐
# ============================================================
music = bus()

def pad(t0, t1, notes, gain=.05, att=1.2, rel=1.5, cutoff=1800, detune=.004):
    n = int((t1 - t0 + rel) * SR); t = tvec(n); out = np.zeros((n, 2))
    for k, nm in enumerate(notes):
        f = note(nm)
        for d, side in ((-detune, 0), (detune, 1), (0, None)):
            ph = 2 * np.pi * f * (1 + d) * t + rng.uniform(0, 6.28)
            saw = sum(np.sin(ph * h) / h for h in range(1, 7))
            v = saw * (.6 if side is None else .45)
            if side is None: out += v[:, None] * .5
            else: out[:, side] += v
    out = lp(out, cutoff, 2)
    e = env_adsr(int((t1 - t0) * SR), att, 0.01)
    e = np.concatenate([e, np.linspace(1, 0, n - len(e)) ** 2])
    lfo = 1 + .08 * np.sin(2 * np.pi * .13 * t)
    put(music, t0, out * (e * lfo)[:, None] / len(notes), gain)

def sub(t0, t1, nm, gain=.22, att=.6, rel=1.0):
    n = int((t1 - t0 + rel) * SR); t = tvec(n); f = note(nm)
    s = np.sin(2 * np.pi * f * t) + .18 * np.sin(4 * np.pi * f * t)
    e = env_adsr(int((t1 - t0) * SR), att, .01); e = np.concatenate([e, np.linspace(1, 0, n - len(e)) ** 2])
    put(music, t0, s * e, gain)

def pluck(t0, nm, gain=.05, dec=1.2, pan=0.0):
    n = int(dec * 2.5 * SR); t = tvec(n); f = note(nm)
    s = sum(np.sin(2 * np.pi * f * h * t) * np.exp(-t * (3 + h * 2.2) / dec) / h ** 1.3 for h in range(1, 6))
    s *= np.minimum(1, t / .004)
    put(music, t0, s, gain, pan)

def pulse_sidechain(t0, t1, depth=.35):
    """八分音符律动：给已有配乐加上节拍性的“呼吸”起伏"""
    i0, i1 = int(t0 * SR), int(t1 * SR); t = tvec(i1 - i0)
    ph = (t / (BEAT / 2)) % 1
    g = 1 - depth * np.exp(-ph * 9)
    music[i0:i1] *= g[:, None].astype(np.float32)

# 段落与和弦（来自原片频谱：F 小调）
SECTIONS = [
    (0.0, 5.0, ['F2', 'C3', 'Ab3', 'G4', 'C5'], 'F1', .16),     # 开场 Fm
    (5.0, 7.2, ['Eb2', 'Bb2', 'Db3', 'G3', 'Eb4'], 'Eb1', .26),  # 撞上核心：Eb7 冲击
    (7.2, 12.4, ['F2', 'C3', 'Ab3', 'G3', 'Eb4', 'C5'], 'F1', .16),
    (12.4, 17.2, ['Db2', 'Ab2', 'Bb2', 'F3', 'Db4', 'Eb4'], None, 0),  # 俯视跑道：悬空，无低音
    (17.2, 31.0, ['F2', 'C3', 'F3', 'Ab3', 'Eb4', 'C5'], 'F1', .24),  # “中途”：低音回归
    (31.0, 34.2, ['Db2', 'Ab2', 'Bb2', 'Bb3', 'C5'], 'Db2', .1),      # 黑场提问
    (34.2, 49.0, ['F2', 'C3', 'F3', 'Ab3', 'Eb4', 'G4'], 'F1', .25),
    (49.0, 61.0, ['F2', 'Ab2', 'C3', 'F3', 'Eb4', 'C5'], 'F1', .23),
    (61.0, 68.4, ['F2', 'E2', 'Bb2', 'C3', 'F3', 'C5'], 'F1', .22),   # 危险：E 还原音的紧张感
    (68.4, 72.8, ['Ab2', 'C3', 'Eb3', 'G3', 'C4', 'G4'], 'Ab1', .14),  # 一座桥：Abmaj7 上扬
    (72.8, 79.5, ['F2', 'C3', 'F3', 'G3', 'Ab3', 'C4'], 'F1', .24),
    (79.5, 86.9, ['Db2', 'Ab2', 'Db3', 'Eb3', 'F3', 'Bb3', 'G4'], 'Db1', .18),  # 超越：Db 利底亚，明亮收尾
]
for t0, t1, ch, s, sg in SECTIONS:
    pad(t0, t1, ch, gain=.075, att=.5 if t0 > 0 else 1.5, rel=.9)
    if s: sub(t0, t1, s, gain=sg * .9, att=.25, rel=.6)

# 拨弦动机（八分音符，F 小调音阶上的分解和弦）
MOTIF = {'Fm': ['F4', 'Ab4', 'C5', 'G4', 'Ab4', 'C5', 'Eb5', 'C5'], 'Eb': ['Eb4', 'G4', 'Bb4', 'Db5'],
         'Db': ['Db4', 'F4', 'Ab4', 'Eb5', 'F4', 'Ab4', 'Bb4', 'C5'], 'Ab': ['Ab4', 'C5', 'Eb5', 'G5', 'C5', 'Eb5', 'G5', 'C6']}
ARP = [(0.6, 4.9, 'Fm', 1), (7.3, 12.2, 'Fm', 2), (12.6, 17.0, 'Db', 2), (17.25, 30.8, 'Fm', 1), (34.5, 48.8, 'Fm', 2),
       (49.2, 60.8, 'Fm', 1), (61.2, 68.2, 'Fm', 1), (68.5, 72.6, 'Ab', 1), (73.0, 79.3, 'Fm', 2), (79.6, 85.5, 'Db', 1)]
for a, b, key, step in ARP:
    seq = MOTIF[key]; k = 0; t = snap(a)
    while t < b:
        pluck(t, seq[k % len(seq)], gain=.07 * (1.15 if key == 'Db' and a > 79 else 1) * (1 if k % 2 == 0 else .6), dec=.45, pan=.35 * np.sin(k * 1.7))
        k += 1; t += BEAT / 4 * step   # 16 分音符的拨弦律动（原片中高频的“颗粒感”）
# 打击乐：细碎的高频 hi-hat（原片频谱里贯穿全片的竖线）
def hat(t0, g=.05, dec=40, pan=0.0):
    n = int(.12 * SR); t = tvec(n)
    put(music, t0, hp(noise(n), 6500) * np.exp(-t * dec), g, pan)
def rim(t0, g=.08):
    n = int(.15 * SR); t = tvec(n)
    put(music, t0, (bp(noise(n), 1200, 5000) * np.exp(-t * 35) + np.sin(2 * np.pi * 330 * t) * np.exp(-t * 60) * .5), g)
def kick(t0, g=.5):
    n = int(.35 * SR); t = tvec(n); f = 45 + 90 * np.exp(-t * 30)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    put(music, t0, s, g)
def snare(t0, g=.2):
    n = int(.3 * SR); t = tvec(n)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * .6
    put(music, t0, (bp(noise(n), 1500, 7000) * np.exp(-t * 16) + body), g)
# 鼓点：逐个 16 分音符位置还原原片的军鼓 / hi-hat / 底鼓（时间与力度来自 drum_hits.json）
last_kick = -9
for t0, kind, v in DRUMS['hits']:
    if kind == 'kick':   # 低频检测会混进贝斯音，只保留明显的、间隔至少一拍的底鼓
        if v < 1.0 or t0 - last_kick < BEAT * .95: continue
        last_kick = t0
    if kind == 'hat': hat(t0, .5 * v, 60, .2 * np.sin(t0 * 7))
    elif kind == 'snare': snare(t0, .32 * v)
    elif kind == 'kick': kick(t0, .8)
# 律动
for a, b in [(17.25, 31.0), (34.5, 49.0), (49.2, 68.3), (73.0, 79.4), (79.6, 86.0)]:
    pulse_sidechain(a, b, .3)
music = reverb(music, decay=1.6, mix=.12)   # 混响要少：声音才会“贴在面前”
# 段落音量自动化：让每秒的响度起伏贴近原片（数值由对比原片响度曲线得到，单位 dB，每秒一个点）
AUTO = [4.4, 1.0, 0.6, 2.3, -2.7, -7.9, -7.1, 0.0, 2.6, 0.3, -1.8, -0.6, -0.5, 2.6, -3.8, 1.4, -2.5, 3.1, -0.7, 4.9, 3.7, 3.9, -0.9, -1.1, -0.1, -0.6, 0.9, -0.6, 5.3, -2.6, -2.0, -3.6, 3.9, 8.0, 2.0, 3.8, 1.8, 1.4, -5.5, 0.1, 0.6, 4.5, -2.4, 1.3, 1.9, 3.2, 0.9, 2.7, -3.0, 0.7, 1.9, 3.3, 4.4, -2.3, 1.4, -3.5, 2.4, -2.9, 2.4, -0.7, 3.6, 0.9, -0.9, 4.1, -3.3, -5.8, -9.7, -2.3, 7.3, 8.0, 7.1, 8.0, 3.2, 7.6, -2.1, 1.7, -3.0, 1.1, -10.0, -10.0, -10.0, -9.4, -3.0, -3.4, -3.6, 4.7, 8.0]
if AUTO:
    curve = np.interp(np.arange(N) / SR, np.arange(len(AUTO)) + .5, AUTO)
    music *= (10 ** (curve / 20))[:, None].astype(np.float32)
music *= np.concatenate([np.ones(int(85.4 * SR)), np.linspace(1, 0, N - int(85.4 * SR)) ** 1.5])[:, None]

# ============================================================
# 2. 音效
# ============================================================
sfx = bus()

def whoosh(t0, dur, f0, f1, gain=.25, att=.6, pan=0.0, q=2.5):
    n = int(dur * SR); x = sweep_bp(noise(n), f0, f1, q)
    e = np.sin(np.pi * np.clip(np.arange(n) / n / att, 0, 1) / 2) ** 2 * np.clip((n - np.arange(n)) / (n * (1 - att) + 1), 0, 1) ** 1.5
    put(sfx, t0, x * e, gain, pan)

def riser(t0, dur, gain=.2):
    n = int(dur * SR); t = tvec(n)
    f = 200 * (12 ** (t / dur)); tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * .3
    x = sweep_bp(noise(n), 400, 9000, 2) + tone
    put(sfx, t0, x * (t / dur) ** 2.2, gain)

def reverse_swell(t1, dur, gain=.3):
    n = int(dur * SR); t = tvec(n)
    x = lp(noise(n), 3000) * .6 + np.sin(2 * np.pi * 80 * t) * .5
    put(sfx, t1 - dur, x * (t / dur) ** 3, gain)

def impact(t0, gain=.7, f0=110, f1=32, dec=1.6, noisy=.5):
    n = int(dec * 2 * SR); t = tvec(n); f = f1 + (f0 - f1) * np.exp(-t * 7)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / dec * 2.2)
    crack = lp(noise(n), 4000) * np.exp(-t * 18) * noisy
    put(sfx, t0, boom + crack, gain)

def gunshot(t0, gain=.9):
    n = int(1.2 * SR); t = tvec(n)
    crack = lp(hp(noise(n), 900), 11000) * np.exp(-t * 60) * 1.4 * np.minimum(1, t / .0015)
    body = lp(noise(n), 1800) * np.exp(-t * 14) * .8
    thump = np.sin(2 * np.pi * 70 * t) * np.exp(-t * 18) * .8
    tail = bp(noise(n), 400, 3000) * np.exp(-t * 3.2) * .12   # 体育场回声
    put(sfx, t0, (crack + body + thump + tail) * np.minimum(1, t / .0015), gain, -.4)

def crowd(t0, dur, gain=.35):
    n = int(dur * SR); t = tvec(n); x = np.zeros(n)
    for v in range(40):  # 40 个“人声”：带通噪声 + 随机抖动的音量
        lo = rng.uniform(300, 900); x += bp(noise(n), lo, lo * rng.uniform(2, 4)) * (1 + .7 * np.sin(2 * np.pi * rng.uniform(3, 8) * t + rng.uniform(0, 6)))
    x /= 8; e = np.minimum(1, t / .25) * np.exp(-np.maximum(0, t - .35) * 1.7)
    st = np.stack([x * e, np.roll(x, 900) * e], 1)
    put(sfx, t0, st, gain)

def breath(t0, dur, inhale=True, gain=.18, pan=0.0):
    n = int(dur * SR); t = tvec(n)
    x = bp(noise(n), 500, 2600) * .7 + bp(noise(n), 1200, 1600, 1) * .5
    e = np.sin(np.pi * t / dur) ** (1.5 if inhale else .8)
    if not inhale: e *= np.exp(-t / dur * 1.2)
    put(sfx, t0, x * e, gain, pan)

def heartbeat(t0, gain=.6):
    for k, (dt, g) in enumerate(((0, 1), (.24, .7))):
        n = int(.35 * SR); t = tvec(n); f = 38 + 30 * np.exp(-t * 25)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) * np.minimum(1, t / .006)
        put(sfx, t0 + dt, lp(s, 200), gain * g)

def page_flip(t0, dur=.45, gain=.3):
    n = int(dur * SR); t = tvec(n)
    swish = sweep_bp(noise(n), 1500, 5000, 1.5) * np.sin(np.pi * t / dur) ** 1.5
    cr = np.zeros(n)
    for _ in range(30):  # 纸张的细碎噼啪
        i = int(rng.uniform(0, n - 400)); cr[i:i + 300] += hp(noise(300), 3000) * np.exp(-np.arange(300) / 60) * rng.uniform(.2, .8)
    put(sfx, t0, swish + cr * np.sin(np.pi * t / dur), gain, rng.uniform(-.3, .3))

def key_click(t0, gain=.12):
    n = int(.05 * SR); t = tvec(n)
    s = bp(noise(n), 1800, 7000) * np.exp(-t * 160) + np.sin(2 * np.pi * 900 * t) * np.exp(-t * 200) * .3
    put(sfx, t0, s, gain * rng.uniform(.7, 1.1), rng.uniform(-.2, .2))

def typing(t0, chars, per):
    for i in range(chars): key_click(t0 + i * per)

def chime(t0, f=880, gain=.12, dec=2.2, pan=0.0):
    n = int(dec * 1.5 * SR); t = tvec(n)
    s = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * (1.6 + r) / dec) for r, a in ((1, 1), (2.76, .5), (5.4, .25), (8.93, .12)))
    put(sfx, t0, s * np.minimum(1, t / .002), gain, pan)

def tone_hit(t0, f, gain=.2, dec=1.5, bright=2000):
    n = int(dec * 1.8 * SR); t = tvec(n)
    s = sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, 8))
    put(sfx, t0, lp(s, bright) * np.exp(-t * 2.4 / dec) * np.minimum(1, t / .01), gain)

def glitch(t0, dur, gain=.3):
    n = int(dur * SR); x = np.zeros(n); fr = int(SR / 30)
    for s in range(0, n, fr):
        k = rng.integers(0, 4); seg = np.arange(min(fr, n - s))
        if k == 0: x[s:s + fr] = np.sign(np.sin(2 * np.pi * rng.uniform(80, 900) * seg / SR)) * .6
        elif k == 1: hold = int(rng.uniform(6, 40)); v = noise(len(seg) // hold + 1); x[s:s + fr] = np.repeat(v, hold)[:len(seg)] * .5
        elif k == 2: x[s:s + fr] = np.sin(2 * np.pi * rng.uniform(1500, 5000) * seg / SR) * .4
    x = np.round(x * 6) / 6  # 降位深
    put(sfx, t0, x, gain)

def footstep(t0, gain=.25, soft=1.0, pan=0.0):
    n = int(.18 * SR); t = tvec(n)
    thud = np.sin(2 * np.pi * (60 + 60 * np.exp(-t * 40)) * t) * np.exp(-t * 30)
    grit = bp(noise(n), 800, 4000) * np.exp(-t * 45) * .4 * soft
    put(sfx, t0, thud + grit, gain, pan)

def creak(t0, dur, gain=.18):
    n = int(dur * SR); t = tvec(n)
    f = 180 + 70 * np.sin(2 * np.pi * .9 * t) + 30 * np.sin(2 * np.pi * 3.1 * t)
    saw = ((np.cumsum(f) / SR) % 1) * 2 - 1
    x = bp(saw * (1 + .5 * noise(n) * .2), 300, 1600) * (.6 + .4 * np.sin(2 * np.pi * 7 * t))
    put(sfx, t0, x * np.sin(np.pi * t / dur) ** .7, gain)

def pebble(t0, gain=.1):
    n = int(.04 * SR); t = tvec(n)
    put(sfx, t0, np.sin(2 * np.pi * rng.uniform(2500, 4500) * t) * np.exp(-t * 180), gain * rng.uniform(.5, 1), rng.uniform(-.3, .3))

def wind(t0, t1, gain=.12):
    n = int((t1 - t0) * SR); t = tvec(n)
    x = lp(noise(n), 700) * (1 + .5 * np.sin(2 * np.pi * .2 * t)) + bp(noise(n), 900, 1400) * .25 * (1 + np.sin(2 * np.pi * .13 * t))
    put(sfx, t0, x * env_adsr(n, 1.0, 1.2), gain)

def shimmer(t0, dur, gain=.1):
    n = int(dur * SR); t = tvec(n); x = np.zeros(n)
    for f in (1046.5, 1318.5, 1568, 2093, 2637):
        x += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (1 + np.sin(2 * np.pi * rng.uniform(4, 9) * t)) / 2
    put(sfx, t0, x * np.sin(np.pi * t / dur) ** 2 / 3, gain)

def soft_hit(t0, gain=.25):  # 字幕关键句的轻击
    n = int(1.2 * SR); t = tvec(n)
    s = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 6) + lp(noise(n), 2500) * np.exp(-t * 25) * .3
    put(sfx, t0, s, gain)

# 只保留原片里能在频谱上找到的设计音效
n = int(.8 * SR); tt = tvec(n)                         # 片头：一口气似的噪声起手
put(sfx, 0.0, bp(noise(n), 700, 5000) * np.exp(-tt * 4) * np.minimum(1, tt / .02), .25)
reverse_swell(5.05, 1.4, .35); impact(5.05, .7, f0=120, f1=34, dec=1.8)   # 白色圆环
def bell(t0, gain, dec=3.0):   # 清脆的金属铃：非谐波泛音 + 快速起音
    n = int(dec * SR); t = tvec(n)
    parts = ((1, 1, 1.0), (2.41, .7, 1.4), (3.89, .5, 2.0), (5.42, .35, 2.8), (6.8, .25, 3.5), (8.93, .15, 4.5))
    s = sum(a * np.sin(2 * np.pi * 1180 * r * t + rng.uniform(0, 6)) * np.exp(-t * k / dec * 2) for r, a, k in parts)
    s = s * (1 + .25 * np.sin(2 * np.pi * 5.5 * t))   # 轻微的拍频颤动
    return s * np.minimum(1, t / .0015)
def echo(x, delay=.23, fb=.45, n=5):   # 回声：几次逐渐变暗、变小的重复
    out = np.concatenate([x, np.zeros(int(delay * SR * n))]); d = int(delay * SR); y = x.copy()
    for k in range(1, n + 1):
        y = lp(y, 9000 - k * 1300, 1) * fb; out[k * d:k * d + len(y)] += y * (1 if k % 2 else .8)
    return out
b = echo(bell(0, 1)); put(sfx, 5.05, b, .16, -.15); put(sfx, 5.05 + .011, b, .16, .15)
n = int(3.2 * SR); tt = tvec(n)                        # 耳鸣：5.2kHz 细长音（原片 5.0–8.0s），震得发蒙
ring_t = np.sin(2 * np.pi * 5200 * tt) * (np.exp(-tt * .9) * .7 + .3 * np.exp(-((tt - 2.4) / .35) ** 2))
put(sfx, 5.0, echo(ring_t, .19, .35, 3), .06)
# “发蒙”：冲击后配乐像被捂住耳朵，1.5 秒内慢慢恢复
i0, i1 = int(5.05 * SR), int(6.8 * SR); seg_ = music[i0:i1].copy(); k = np.linspace(0, 1, i1 - i0)[:, None] ** 1.5
music[i0:i1] = lp(seg_, 500, 2) * (1 - k) * 1.4 + seg_ * k
for i, ts in enumerate([7.35, 7.6, 7.85, 8.1]):        # 权 力 意 志：一个个砸下来
    n = int(1.0 * SR); tt = tvec(n)
    thud = np.sin(2 * np.pi * (48 + 70 * np.exp(-tt * 28)) * tt) * np.exp(-tt * 7)
    crack = lp(hp(noise(n), 1500), 9000) * np.exp(-tt * 45) * .5 * np.minimum(1, tt / .001)
    put(sfx, ts - .01, thud + crack, .5 + .06 * i)
whoosh(11.6, 2.8, 600, 10000, .24, att=.25)           # 抬镜头 → 俯视跑道：起势后长长的风声（原片 11.6–14.4s）
gunshot(15.43, .5)                                    # 发令枪
n = int(1.6 * SR); tt = tvec(n)                        # 发令枪之后的场馆回响
put(sfx, 15.55, bp(noise(n), 800, 6000) * np.exp(-tt * 2.2) * np.minimum(1, tt / .15), .12)
whoosh(18.5, 1.7, 7000, 400, .24, att=.55)            # 跑道卷成书
whoosh(24.4, 1.1, 800, 6000, .2, att=.5)              # 书合上又摊开
page_flip(26.91, .5, .22); page_flip(27.22, .5, .2); page_flip(27.57, .4, .16)
n = int(1.9 * SR); tt = tvec(n)                       # 墨迹吞没：下沉的低频
put(sfx, 29.25, (lp(noise(n), 300) * .8 + np.sin(2 * np.pi * (60 - 25 * tt / 1.9) * tt)) * (tt / 1.9) ** 1.5, .3)
impact(30.41, .22, f0=70, f1=30, dec=1.2, noisy=.1)
n = int(3 * SR); tt = tvec(n)                         # 红色巨影：暗沉的低频
put(sfx, 37.4, (np.sin(2 * np.pi * 41 * tt) + .4 * np.sin(2 * np.pi * 61.7 * tt)) * np.sin(np.pi * tt / 3) ** 2, .22)
whoosh(42.1, .8, 300, 3000, .16, att=.6)               # 站直
reverse_swell(49.19, 1.0, .22); impact(49.19, .4, f0=100, f1=38, dec=1.4)  # 两个声音相撞
whoosh(54.1, 1.2, 9000, 300, .24, att=.35)             # 地面塌成深渊
n = int(1.4 * SR); tt = tvec(n)                         # 绳索下坠：1–3kHz 的摩擦声
put(sfx, 62.3, bp(noise(n), 900, 3000) * np.sin(np.pi * tt / 1.4) ** 2 * (1 + .5 * np.sin(2 * np.pi * 7 * tt)), .14)
reverse_swell(65.75, .7, .25); impact(65.75, .35, f0=90, f1=40, dec=1.2, noisy=.15)
riser(68.0, .9, .1); impact(68.6, .25, f0=80, f1=40, dec=1.0, noisy=.3)   # 绳索变成桥
whoosh(72.3, 1.0, 5000, 500, .2, att=.4)              # 桥落下
impact(72.99, .3, f0=80, f1=40, dec=1.0, noisy=.25)
whoosh(75.0, 1.2, 5000, 700, .2, att=.4)               # 镜头抬起
riser(77.8, 1.8, .26)                                 # 冲进光带
impact(79.6, .55, f0=110, f1=36, dec=1.4)
glitch(82.95, .45, .16)                               # 超越：故障闪烁
whoosh(83.0, 1.4, 800, 8000, .22, att=.4)
sfx = reverb(sfx, decay=1.3, mix=.1, bright=8000)

# ============================================================
# 3. 混音与输出
# ============================================================
def norm_rms(x, db): r = np.sqrt(np.mean(x ** 2)) + 1e-9; return x * (10 ** (db / 20) / r)
music = norm_rms(music, -21.5)
sfx = norm_rms(sfx, -23)
mix = music + sfx
# 匹配原片的整体频谱平衡（按倍频程对比原片后得到的 EQ，单位 dB）
EQ_F = [0, 42, 85, 175, 350, 700, 1400, 2800, 5600, 11000, SR / 2]
EQ_G = [2.2, 2.2, -3.0, 7.7, 11.2, 3.9, -6.8, -3.4, -3.9, -7.8, -8.8]
fir = ss.firwin2(4097, np.array(EQ_F) / (SR / 2), 10 ** (np.array(EQ_G) / 20))
mix = np.stack([ss.fftconvolve(mix[:, c], fir, 'same') for c in range(2)], 1)
# 简单的总线压缩 + 软削波
env = np.sqrt(lp(np.mean(mix ** 2, 1), 8, 1).clip(1e-9))
gain = np.minimum(1, (10 ** (-14 / 20)) / env) ** .5
mix = np.tanh(mix * 1.1) / 1.1   # 不做总线压缩：保留鼓点的冲击力（离得近）
mix *= 10 ** (-3 / 20) / np.abs(mix).max()
fade = np.ones(N); fade[:int(.05 * SR)] = np.linspace(0, 1, int(.05 * SR)); mix *= fade[:, None]
for name, x in (('music', music), ('sfx', sfx), ('mix', mix)):
    y = x / max(1, np.abs(x).max() / .98)
    wf.write(f'{name}.wav', SR, (y * 32767).astype(np.int16))
print('rms dB', 20 * np.log10(np.sqrt(np.mean(mix ** 2))))
