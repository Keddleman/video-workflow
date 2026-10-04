"""9:16 Reel renderer: original background, speaker cutout over logo pops, captions, banners, CTA.

    python3 reel.py timeline.json src.mp4 alpha.mp4 logos/ out_video.mp4 [test t1,t2,...]

The speaker matte (alpha.mp4, any size) comes from matte.py. Logos are drawn *behind* the speaker
so they appear to rise from behind the head; text is drawn in front.
"""
import os, sys, json, math, subprocess, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
cv2.setNumThreads(1)
W, H, FPS = 1080, 1920, 30
FONT = os.environ.get('FONT', '/usr/share/fonts/truetype/higgsfield/Montserrat-ExtraBold.ttf')
TL = json.load(open(sys.argv[1])); SRC, ALPHA, LOGO, OUT = sys.argv[2:6]
words = TL['words']; DUR = TL['duration']; BR = TL['brands']
NF = int(round(DUR * FPS))

_fc = {}
def font(sz):
    if sz not in _fc: _fc[sz] = ImageFont.truetype(FONT, sz)
    return _fc[sz]
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def eob(x, s=1.9):
    x = clamp(x) - 1; return 1 + (s + 1) * x ** 3 + s * x ** 2
def eo(x): x = clamp(x); return 1 - (1 - x) ** 3
def hexc(h): h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def lerp(a, b, u): return a + (b - a) * u

# ---------- assets ----------
_cache = {}
def tile(key, size):
    k = ('tile', key, size)
    if k in _cache: return _cache[k]
    b = BR[key]; c = hexc(b['color'])
    path = f"{LOGO}/{b['domain']}.png"
    ic = Image.open(path).convert('RGBA') if os.path.exists(path) else Image.new('RGBA', (256, 256), c + (255,))
    pad = int(size * 0.35); S = size + 2 * pad; Ht = S + int(size * 0.32); r = int(size * 0.24)
    im = Image.new('RGBA', (S, Ht), (0, 0, 0, 0))
    g = Image.new('L', (S, Ht), 0)
    ImageDraw.Draw(g).rounded_rectangle([pad - 6, pad - 6, pad + size + 6, pad + size + 6], radius=r, fill=255)
    glow = Image.new('RGBA', (S, Ht), c + (0,)); glow.putalpha(g.filter(ImageFilter.GaussianBlur(size * 0.13)))
    im.alpha_composite(glow)
    mask = Image.new('L', (size, size), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=255)
    t = Image.new('RGBA', (size, size), (255, 255, 255, 255))
    icr = ic.resize((size, size), Image.LANCZOS)
    if np.array(icr)[3, 3][3] > 200: t.alpha_composite(icr)
    else:
        ins = int(size * 0.74); t.alpha_composite(ic.resize((ins, ins), Image.LANCZOS), ((size - ins) // 2, (size - ins) // 2))
    t.putalpha(mask); im.alpha_composite(t, (pad, pad))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([pad, pad, pad + size - 1, pad + size - 1], radius=r, outline=(255, 255, 255, 240), width=max(4, size // 40))
    f = font(int(size * 0.19)); tw = d.textlength(b['name'], font=f)
    pw = tw + size * 0.26; ph = size * 0.29; x0 = S / 2 - pw / 2; y0 = pad + size + size * 0.07
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, fill=(12, 12, 22, 240), outline=c + (255,), width=4)
    d.text((S / 2, y0 + ph / 2), b['name'], font=f, fill=(255, 255, 255, 255), anchor='mm')
    _cache[k] = (im, (S / 2, pad + size / 2)); return _cache[k]

def pill(text, sz, bg, fg=(0, 0, 0)):
    k = ('pill', text, sz, bg)
    if k in _cache: return _cache[k]
    f = font(sz); tw = ImageDraw.Draw(Image.new('L', (1, 1))).textlength(text, font=f)
    pw, ph = int(tw + sz * 1.1), int(sz * 1.55); pad = int(sz * 0.6)
    im = Image.new('RGBA', (pw + 2 * pad, ph + 2 * pad), (0, 0, 0, 0))
    g = Image.new('L', im.size, 0); ImageDraw.Draw(g).rounded_rectangle([pad, pad, pad + pw, pad + ph], radius=ph / 2, fill=255)
    gl = Image.new('RGBA', im.size, bg + (0,)); gl.putalpha(g.filter(ImageFilter.GaussianBlur(sz * 0.35))); im.alpha_composite(gl)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([pad, pad, pad + pw, pad + ph], radius=ph / 2, fill=bg + (255,), outline=(255, 255, 255, 255), width=max(3, sz // 14))
    d.text((pad + pw / 2, pad + ph / 2 + 1), text, font=f, fill=fg + (255,), anchor='mm')
    _cache[k] = (im, (im.size[0] / 2, im.size[1] / 2)); return _cache[k]

def paste(dst, im, cx, cy, alpha=1.0, scale=1.0, rot=0.0, anchor=None):
    if alpha <= 0.01 or scale <= 0.02: return
    ax, ay = anchor if anchor else (im.size[0] / 2, im.size[1] / 2)
    if scale != 1.0:
        im = im.resize((max(1, int(im.size[0] * scale)), max(1, int(im.size[1] * scale))), Image.BILINEAR); ax *= scale; ay *= scale
    if abs(rot) > 0.3:
        w0, h0 = im.size; im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        dx, dy = ax - w0 / 2, ay - h0 / 2; th = math.radians(rot)
        ax = im.size[0] / 2 + dx * math.cos(th) + dy * math.sin(th); ay = im.size[1] / 2 - dx * math.sin(th) + dy * math.cos(th)
    a = np.asarray(im, dtype=np.float32)
    x0, y0 = int(round(cx - ax)), int(round(cy - ay))
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x0 + a.shape[1]), min(H, y0 + a.shape[0])
    if X1 <= X0 or Y1 <= Y0: return
    a = a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]; al = a[..., 3:4] * (alpha / 255.0)
    reg = dst[Y0:Y1, X0:X1]; reg *= (1 - al); reg += a[..., :3] * al

# ---------- logos (behind speaker) ----------
ROW_X = {1: [540], 2: [270, 810], 3: [250, 540, 830], 4: [200, 413, 627, 840], 5: [150, 345, 540, 735, 930]}
ROW_DY = {1: [0], 2: [0, 0], 3: [40, 0, 40], 4: [45, 10, 10, 45], 5: [60, 15, 0, 15, 60]}
POPS = []
for gi, g in enumerate(TL['groups']):
    n = len(g['items']); size = {'row': 165, 'pair': 205, 'solo': 215}[g['layout']]
    for idx, it in enumerate(g['items']):
        POPS.append(dict(key=it['brand'], t_in=it['t'], t_out=g['t_out'], g=gi, n=n, idx=idx, size=size,
                         pulses=[p['t'] for p in g['pulses'] if p['brand'] == it['brand']]))
def slot(p, T, X):
    base = clamp(T - 165, 250, 640)
    return ROW_X[p['n']][p['idx']] + (X - 540) * 0.12, base + ROW_DY[p['n']][p['idx']] - (10 if p['n'] == 1 else 0)
def logo_state(p, t, T, X):
    u = t - p['t_in']
    if u < 0 or t > p['t_out'] + 0.35: return None
    sx, sy = slot(p, T, X); k = eob(u / 0.42, 1.4)
    x = lerp(X, sx, k); y = lerp(T + 260, sy, k) - 120 * math.sin(math.pi * clamp(u / 0.42))
    sc = lerp(0.25, 1.0, eob(u / 0.42, 2.2)); rot = 14 * math.exp(-4 * u) * math.sin(15 * u)
    if u > 0.42: y += 9 * math.sin(2 * math.pi * 0.55 * t + p['idx'] * 1.3); rot += 2.5 * math.sin(2 * math.pi * 0.4 * t + p['idx'])
    for pt in p['pulses']:
        if 0 <= t - pt < 0.6: sc *= 1 + 0.28 * math.exp(-(t - pt) * 6) * abs(math.sin((t - pt) * 12))
    al = 1.0
    if t > p['t_out']:
        w = clamp((t - p['t_out']) / 0.35); y -= 500 * w * w; sc *= 1 - 0.7 * w; al = 1 - w
    return x, y, sc, rot, al, u
def draw_logos(fr, t, T, X):
    st = [(p, s) for p in POPS for s in [logo_state(p, t, T, X)] if s]
    for gi, g in enumerate(TL['groups']):                       # chips + dashed connector lines
        c = g.get('chip')
        if not c or not (c['t'] <= t < g['t_out'] + 0.3): continue
        cx, cy = 540 + (X - 540) * 0.1, clamp(T - 165, 250, 640) + 10
        lay = np.zeros((H, W), np.float32); used = False
        for p, s in st:
            if p['g'] != gi or s[5] < 0.42 or s[4] < 0.5 or p['n'] == 1: continue
            x0, y0, x1, y1 = cx, cy, s[0], s[1]; L = math.hypot(x1 - x0, y1 - y0); off = (t * 260) % 44
            for d0 in np.arange(-44 + off, L, 44):
                d1 = min(L, d0 + 22); d0 = max(0, d0)
                if d1 > d0:
                    cv2.line(lay, (int(x0 + (x1 - x0) * d0 / L), int(y0 + (y1 - y0) * d0 / L)), (int(x0 + (x1 - x0) * d1 / L), int(y0 + (y1 - y0) * d1 / L)), 1.0, 7, cv2.LINE_AA); used = True
        if used: fr += np.clip(lay + cv2.GaussianBlur(lay, (0, 0), 7) * 1.5, 0, 1)[..., None] * np.array([120, 230, 255], np.float32) * 0.9
        u = t - c['t']; w = clamp((t - g['t_out']) / 0.3)
        im, _ = pill(c['text'], 46, hexc(c['bg']), hexc(c['fg']))
        paste(fr, im, cx, cy - 300 * w * w - (90 if all(p['n'] == 1 for p, _ in st if p['g'] == gi) else 0), clamp(u / 0.1) * (1 - w), eob(u / 0.35, 2.5) * (1 - 0.6 * w))
    for p, (x, y, sc, rot, al, u) in st:
        im, anc = tile(p['key'], p['size'])
        if u < 0.42:
            for gg in (3, 2, 1):
                s2 = logo_state(p, t - 0.035 * gg, T, X)
                if s2: paste(fr, im, s2[0], s2[1], 0.22 / gg, s2[2], s2[3], anchor=anc)
        paste(fr, im, x, y, al, sc, rot, anchor=anc)
        if 0.36 < u < 0.9:
            v = (u - 0.36) / 0.54; rr = int(p['size'] * (0.6 + 0.9 * eo(v))); lay = np.zeros((H, W), np.float32)
            cv2.circle(lay, (int(x), int(y)), rr, 1.0, max(2, int(12 * (1 - v))), cv2.LINE_AA)
            for q in range(8):
                a2 = q * math.pi / 4 + 0.3; r1, r2 = rr * 1.05, rr * (1.05 + 0.35 * (1 - v))
                cv2.line(lay, (int(x + r1 * math.cos(a2)), int(y + r1 * math.sin(a2))), (int(x + r2 * math.cos(a2)), int(y + r2 * math.sin(a2))), 1.0, 6, cv2.LINE_AA)
            fr += lay[..., None] * np.array(hexc(BR[p['key']]['color']), np.float32) * (1 - v) * 1.2

# ---------- summary cards (optional, behind speaker) ----------
CARDS = TL.get('cards')
if CARDS:
    rng = np.random.default_rng(3)
    def make_card(title, seed):
        r = np.random.default_rng(seed); w, h = 210, 260
        im = Image.new('RGBA', (w + 40, h + 40), (0, 0, 0, 0))
        sh = Image.new('L', im.size, 0); ImageDraw.Draw(sh).rounded_rectangle([24, 28, 24 + w, 28 + h], 18, fill=150)
        im.putalpha(sh.filter(ImageFilter.GaussianBlur(10))); d = ImageDraw.Draw(im)
        d.rounded_rectangle([20, 20, 20 + w, 20 + h], 18, fill=(250, 250, 252, 240))
        d.rounded_rectangle([20, 20, 20 + w, 70], 18, fill=(60, 64, 80, 255)); d.rectangle([20, 50, 20 + w, 70], fill=(60, 64, 80, 255))
        d.text((20 + w / 2, 46), title, font=font(24), fill=(255, 255, 255, 255), anchor='mm')
        for k in range(7):
            d.rounded_rectangle([40, 92 + k * 24, 40 + r.uniform(0.45, 0.92) * (w - 40), 104 + k * 24], 6, fill=(185, 190, 205, 255))
        return im
    titles = CARDS.get('titles', ['SUMMARY'])
    CIM = [make_card(titles[k % len(titles)], k) for k in range(16)]
    CX, CY, CROT, CPH = rng.uniform(110, 970, 16), rng.uniform(380, 1500, 16), rng.uniform(-18, 18, 16), rng.uniform(0, 6.28, 16)
def draw_cards(fr, t):
    if not CARDS or t < CARDS['t_in'] or t > CARDS['collapse'] + 3: return
    for k in range(16):
        ts = CARDS['t_in'] + 0.32 * k
        if t < ts or ts > CARDS['collapse']: continue
        x = CX[k] + 18 * math.sin(t * 0.8 + CPH[k]); y = CY[k] + 14 * math.cos(t * 0.6 + CPH[k])
        sc = 0.75 * eob((t - ts) / 0.35); rot = CROT[k] + 6 * math.sin(t + CPH[k]); al = 0.95
        ss = CARDS['collapse'] + 0.12 * k
        if t > ss:
            v = clamp((t - ss) / 0.55); e = v * v
            x, y = lerp(x, 540, e), lerp(y, 300, e); sc *= (1 - 0.9 * e); rot += 540 * e; al = 1 - v ** 4
            if v >= 1: continue
        paste(fr, CIM[k], x, y, al, sc, rot)

# ---------- banners, CTA, captions (in front) ----------
def banner_img(lbl, col, txt):
    k = ('ban', lbl, txt)
    if k in _cache: return _cache[k]
    txt = txt.replace('<br>', ' ').upper()
    im = Image.new('RGBA', (W, 300), (0, 0, 0, 0)); c = hexc(col)
    p, _ = pill(lbl, 40, c, (0, 0, 0) if sum(c) > 500 else (255, 255, 255)); im.alpha_composite(p, (int(W / 2 - p.size[0] / 2), 0))
    sz = 80
    while ImageDraw.Draw(im).textlength(txt, font=font(sz)) > 990: sz -= 4
    sh = Image.new('L', im.size, 0); ImageDraw.Draw(sh).text((W / 2 + 4, 200), txt, font=font(sz), fill=210, anchor='mm', stroke_width=12, stroke_fill=210)
    s = Image.new('RGBA', im.size, (0, 0, 0, 0)); s.putalpha(sh.filter(ImageFilter.GaussianBlur(10))); im.alpha_composite(s)
    ImageDraw.Draw(im).text((W / 2, 194), txt, font=font(sz), fill=(255, 255, 255, 255), anchor='mm', stroke_width=8, stroke_fill=(0, 0, 0, 255))
    _cache[k] = im; return im
def draw_banner(fr, t):
    for b in TL['banners']:
        if b['t_in'] <= t < b['t_out']:
            u, v = t - b['t_in'], b['t_out'] - t
            paste(fr, banner_img(b['label'], b.get('color', '#10B981'), b['text']), W / 2, 330, clamp(u / 0.2) * clamp(v / 0.2), 0.7 + 0.3 * eob(u / 0.3), anchor=(W / 2, 110))

def make_cta():
    w, h, pad = 860, 400, 70
    im = Image.new('RGBA', (w + 2 * pad, h + 2 * pad + 60), (0, 0, 0, 0))
    m = Image.new('L', im.size, 0); dm = ImageDraw.Draw(m)
    dm.rounded_rectangle([pad, pad, pad + w, pad + h], 60, fill=255)
    dm.polygon([(pad + 140, pad + h - 10), (pad + 120, pad + h + 70), (pad + 260, pad + h - 10)], fill=255)
    glow = Image.new('RGBA', im.size, (255, 200, 40, 0)); glow.putalpha(m.filter(ImageFilter.GaussianBlur(30))); im.alpha_composite(glow)
    gy = np.linspace(0, 1, im.size[1])[:, None, None]
    grad = np.zeros((im.size[1], im.size[0], 4), np.uint8)
    grad[..., :3] = (np.array([255, 230, 80]) * (1 - gy) + np.array([255, 150, 30]) * gy).astype(np.uint8)
    grad[..., 3] = np.array(m); im.alpha_composite(Image.fromarray(grad))
    d = ImageDraw.Draw(im); kw = TL.get('cta_big') or TL['keyword'] or 'NOW'
    d.rounded_rectangle([pad, pad, pad + w, pad + h], 60, outline=(255, 255, 255, 255), width=10)
    tsz = 66
    while d.textlength(TL.get('cta_top', 'COMMENT'), font=font(tsz)) > w - 80: tsz -= 4
    d.text((pad + w / 2, pad + 85), TL.get('cta_top', 'COMMENT'), font=font(tsz), fill=(30, 20, 0, 255), anchor='mm')
    ksz = 178
    while d.textlength(kw, font=font(ksz)) > w - 80: ksz -= 8
    d.text((pad + w / 2, pad + 215), kw, font=font(ksz), fill=(0, 0, 0, 255), anchor='mm')
    d.text((pad + w / 2, pad + 335), TL['cta_line'], font=font(46), fill=(60, 30, 0, 255), anchor='mm')
    return im
CTA = make_cta() if TL['slams'] else None
def cta_state(t):
    for a, b in TL['slams']:
        if a <= t < b: return t - a, b - t
    return None
def draw_cta(fr, t):
    s = cta_state(t)
    if not s: return
    u, v = s
    sc = (1 + 1.3 * (1 - eo(u / 0.2))) * (1 + 0.035 * max(0, math.sin(2 * math.pi * 1.7 * u)) ** 4) * clamp(v / 0.25) ** 0.5
    paste(fr, CTA, W / 2, 1300, clamp(u / 0.05) * clamp(v / 0.2), sc * 0.9, 3 * math.sin(u * 2.2))

KEYC = {BR[k]['name'].upper().replace(' ', ''): hexc(BR[k]['caption']) for k in BR}
KW = TL['keyword']
def clean(w): return w.strip().upper().replace(',', '').replace('.', '')
chunks, cur = [], []
for i, (s, e, w) in enumerate(words):
    if cur and (len(cur) >= 3 or s - words[cur[-1]][1] > 0.3): chunks.append(cur); cur = []
    cur.append(i)
    if w.strip() and w.strip()[-1] in '.,?!': chunks.append(cur); cur = []
if cur: chunks.append(cur)
CH = []
for j, c in enumerate(chunks):
    st = words[c[0]][0]; en = words[c[-1]][1] + 0.5
    if j + 1 < len(chunks): en = min(en, words[chunks[j + 1][0]][0])
    CH.append((st, en, c))
def caption_img(j, act):
    k = ('cap', j, act)
    if k in _cache: return _cache[k]
    c = CH[j][2]; toks = [clean(words[i][2]) for i in c]; base = 88
    while True:
        f, fa, gap = font(base), font(int(base * 1.14)), base * 0.28
        ws = [ImageDraw.Draw(Image.new('L', (1, 1))).textlength(tk, font=fa if c[n] == act else f) for n, tk in enumerate(toks)]
        tot = sum(ws) + gap * (len(ws) - 1)
        if tot < 980 or base < 50: break
        base -= 6
    im = Image.new('RGBA', (W, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(im); cy = 150
    sh = Image.new('L', im.size, 0); ds = ImageDraw.Draw(sh); x = W / 2 - tot / 2
    for n, tk in enumerate(toks):
        ds.text((x + ws[n] / 2 + 5, cy + 8), tk, font=fa if c[n] == act else f, fill=200, anchor='mm', stroke_width=12, stroke_fill=200); x += ws[n] + gap
    s = Image.new('RGBA', im.size, (0, 0, 0, 0)); s.putalpha(sh.filter(ImageFilter.GaussianBlur(9))); im.alpha_composite(s)
    x = W / 2 - tot / 2
    for n, tk in enumerate(toks):
        ff = fa if c[n] == act else f; key = tk.strip('?!')
        if KW and key == KW:
            bb = d.textbbox((x + ws[n] / 2, cy), tk, font=ff, anchor='mm')
            d.rounded_rectangle([bb[0] - 16, bb[1] - 14, bb[2] + 16, bb[3] + 14], 18, fill=(250, 204, 21, 255))
            d.text((x + ws[n] / 2, cy), tk, font=ff, fill=(0, 0, 0, 255), anchor='mm')
        else:
            col = KEYC.get(key.replace("'S", ''), (255, 225, 77) if c[n] == act else (255, 255, 255))
            d.text((x + ws[n] / 2, cy), tk, font=ff, fill=col + (255,), anchor='mm', stroke_width=9, stroke_fill=(0, 0, 0, 255))
        x += ws[n] + gap
    _cache[k] = im; return im
def draw_caption(fr, t):
    if cta_state(t): return
    for j, (st, en, c) in enumerate(CH):
        if st <= t < en:
            act = c[0]
            for i in c:
                if words[i][0] <= t: act = i
            u = t - st; paste(fr, caption_img(j, act), W / 2, 1430, clamp(u / 0.06), 0.82 + 0.18 * eob(u / 0.16)); return

# ---------- head tracking + compositing ----------
def head_track():
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', ALPHA, '-vf', 'scale=90:160', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
    A = np.frombuffer(raw, np.uint8).reshape(-1, 160, 90); T, X = [], []
    for a in A:
        m = a > 128; rows = np.where(m.sum(1) >= 3)[0]
        if len(rows) == 0: T.append(T[-1] if T else 40); X.append(X[-1] if X else 45); continue
        t0 = rows[0]; yy, xx = np.nonzero(m[t0:t0 + 12]); T.append(t0); X.append(xx.mean())
    T, X = np.array(T, float) * 12, np.array(X, float) * 12; k = 25; ker = np.ones(k) / k
    sm = lambda v: np.convolve(np.pad(v, (k // 2, k // 2), mode='edge'), ker, mode='valid')
    T, X = sm(T), sm(X)
    if len(T) < NF + 2: T = np.pad(T, (0, NF + 2 - len(T)), mode='edge'); X = np.pad(X, (0, NF + 2 - len(X)), mode='edge')
    return T, X

def compose(fi, rgb, a, T, X):
    t = fi / FPS; tt, xx = T[fi], X[fi]; hy = tt + 300
    fr = rgb.astype(np.float32).copy()
    draw_cards(fr, t); draw_logos(fr, t, tt, xx)
    a3 = a[..., None]; fr = rgb.astype(np.float32) * a3 + fr * (1 - a3)
    draw_banner(fr, t); draw_cta(fr, t); draw_caption(fr, t)
    z = 1.0
    for e in TL['zooms']:
        u = t - e
        if 0 <= u < 1.2: z += 0.06 * min(1, u / 0.06) * math.exp(-u * 3.5)
    dx = dy = flash = 0.0; s = cta_state(t)
    if s and s[0] < 0.5:
        u = s[0]; dx = 26 * math.exp(-u * 9) * math.sin(u * 63); dy = 26 * math.exp(-u * 9) * math.cos(u * 51); flash = 0.55 * math.exp(-u * 14)
    if z > 1.001 or abs(dx) > 0.3:
        fr = cv2.warpAffine(fr, np.float32([[z, 0, (1 - z) * xx + dx], [0, z, (1 - z) * hy + dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    if flash > 0.01: fr = fr * (1 - flash) + 255 * flash
    return np.clip(fr, 0, 255).astype(np.uint8)

SCALE = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}'
TONEMAP = os.environ.get('TONEMAP', '')   # set by run.sh for HDR (HLG/PQ) sources
def readers(f0, n):
    ss = f'{f0 / FPS:.4f}'
    v = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', ss, '-i', SRC, '-map', '0:v:0', '-frames:v', str(n), '-vf', (TONEMAP + ',' if TONEMAP else '') + SCALE, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    al = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', ss, '-i', ALPHA, '-frames:v', str(n), '-vf', f'scale={W}:{H}:flags=bicubic', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    return v, al
def prep_alpha(b): return np.clip((np.frombuffer(b, np.uint8).reshape(H, W).astype(np.float32) / 255 - 0.06) / 0.88, 0, 1)

def render_range(args):
    f0, f1, out, T, X = args; v, al = readers(f0, f1 - f0)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'fast', '-crf', '17', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    last = None
    for fi in range(f0, f1):
        b = v.stdout.read(W * H * 3); ba = al.stdout.read(W * H)
        if len(b) < W * H * 3:
            if last is None: break
            b = last[0]
        if len(ba) < W * H: ba = last[1] if last else bytes(W * H)
        last = (b, ba)
        enc.stdin.write(compose(fi, np.frombuffer(b, np.uint8).reshape(H, W, 3), prep_alpha(ba), T, X).tobytes())
    enc.stdin.close(); enc.wait(); return out

if __name__ == '__main__':
    T, X = head_track()
    if len(sys.argv) > 7 and sys.argv[6] == 'test':
        for ts in [float(x) for x in sys.argv[7].split(',')]:
            fi = int(ts * FPS); v, al = readers(fi, 1)
            out = compose(fi, np.frombuffer(v.stdout.read(W * H * 3), np.uint8).reshape(H, W, 3), prep_alpha(al.stdout.read(W * H)), T, X)
            Image.fromarray(out).resize((360, 640), Image.LANCZOS).save(f'reel_test_{ts:05.2f}.jpg', quality=82)
        sys.exit(0)
    from multiprocessing import Pool
    NW = int(os.environ.get('NW', '5')); step = math.ceil(NF / NW); d = os.path.dirname(os.path.abspath(OUT))
    jobs = [(i * step, min(NF, (i + 1) * step), f'{d}/reel_chunk{i}.mp4', T, X) for i in range(NW)]
    with Pool(NW) as p: outs = p.map(render_range, jobs)
    open(f'{d}/reel_list.txt', 'w').write(''.join(f"file '{o}'\n" for o in outs))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{d}/reel_list.txt', '-c', 'copy', OUT], check=True)
    for o in outs: os.remove(o)
    print('REEL OK', OUT)
