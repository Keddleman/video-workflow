"""Synthesised sound effects from the timeline. python3 sfx.py timeline.json sfx.wav
whoosh+pop on every logo, pop on chips, bass hit on each CTA slam, soft whoosh on headlines/cards."""
import sys, json, wave, numpy as np
TL = json.load(open(sys.argv[1])); sr = 48000; n = int(sr * (TL['duration'] + 1)); out = np.zeros(n); rng = np.random.default_rng(1)
def add(t, s):
    i = max(0, int(t * sr)); j = min(n, i + len(s)); out[i:j] += s[:j - i]
def whoosh(d=0.42):
    m = int(sr * d); x = rng.standard_normal(m); y = np.zeros(m); a = np.linspace(0.02, 0.35, m) ** 1.5; s = 0.0
    for k in range(m): s += a[k] * (x[k] - s); y[k] = s
    return y * np.sin(np.pi * np.linspace(0, 1, m)) ** 2 / (np.abs(y).max() + 1e-9)
def pop():
    m = int(sr * 0.09); tt = np.arange(m) / sr; f = np.linspace(1100, 380, m); return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 45)
def boom():
    m = int(sr * 0.7); tt = np.arange(m) / sr; f = np.linspace(120, 42, m)
    return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 6) + 0.4 * rng.standard_normal(m) * np.exp(-tt * 30)
W, P, B = whoosh(), pop(), boom(); WS = whoosh(0.3)
for g in TL['groups']:
    for it in g['items']: add(it['t'] - 0.05, 0.22 * W); add(it['t'] + 0.36, 0.30 * P)
    if g.get('chip'): add(g['chip']['t'], 0.25 * P)
for a, b in TL['slams']: add(a, 0.5 * B)
for b in TL['banners']: add(b['t_in'] - 0.1, 0.15 * WS)
if TL.get('cards') and TL['cards'].get('result_in'): add(TL['cards']['result_in'] - 0.1, 0.15 * WS)
out = np.clip(out, -1, 1)
w = wave.open(sys.argv[2], 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
w.writeframes((out * 32767).astype('<i2').tobytes()); w.close(); print('SFX OK')
