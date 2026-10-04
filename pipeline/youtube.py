"""16:9 YouTube composition (HyperFrames). Writes index.html into the project dir.

    python3 youtube.py timeline.json project_dir/

Layout: speaker video full-height in the centre; blurred, darkened copy of the real room on the
sides (plate.mp4, built by run.sh); logos pop into the side panels; headlines + end-steps on the
left; summary cards on the right; captions + CTA bottom-centre.
"""
import json, sys, random, os
TL = json.load(open(sys.argv[1])); PROJ = sys.argv[2]
words = TL['words']; DUR = TL['duration']; BR = TL['brands']; KW = TL['keyword']
L, R = 328, 1592
H, J = [], []
def js(s): J.append(s)

H.append(f'<video id="plate" src="plate.mp4" data-start="0" data-duration="{DUR}" data-track-index="0" muted playsinline></video>')
H.append(f'<div id="ov" class="clip" data-start="0" data-duration="{DUR}" data-track-index="1">')
H.append('<div class="col"></div>')

# ---- logo layout per group ----
SIDE_Y = {1: [470], 2: [330, 640], 3: [270, 560, 850]}
tiles = []   # (gi, brand, t_in, t_out, x, y, size, pulses)
for gi, g in enumerate(TL['groups']):
    its = g['items']
    if g['layout'] == 'row':
        left, right = its[0::2], its[1::2]
        for side, x in ((left, L), (right, R)):
            for k, it in enumerate(side):
                tiles.append((gi, it, x, SIDE_Y[len(side)][k], 190))
    elif g['layout'] == 'pair':
        tiles.append((gi, its[0], L, 470, 300)); tiles.append((gi, its[1], R, 470, 300))
    else:
        tiles.append((gi, its[0], R, 470, 300))
for i, (gi, it, x, y, s) in enumerate(tiles):
    g = TL['groups'][gi]; b = BR[it['brand']]; ti, to = it['t'], g['t_out']
    H.append(f'<div class="tile" id="t{i}" style="left:{x - s/2}px;top:{y - s/2}px;width:{s}px;--c:{b["color"]}">'
             f'<div class="ic" style="width:{s}px;height:{s}px;border-radius:{s*.24}px"><img src="logos/{b["domain"]}.png"></div>'
             f'<div class="lab" style="font-size:{s*.15}px">{b["name"]}</div><div class="ring" style="width:{s}px;height:{s}px"></div></div>')
    sx = 1 if x < 960 else -1
    js(f"tl.fromTo('#t{i}',{{autoAlpha:0,scale:.2,x:{-sx*420},y:120,rotation:{-sx*25}}},{{autoAlpha:1,scale:1,x:0,y:0,rotation:0,duration:.5,ease:'back.out(1.8)'}},{ti})")
    js(f"tl.fromTo('#t{i} .ring',{{scale:.8,autoAlpha:1}},{{scale:1.9,autoAlpha:0,duration:.6,ease:'power2.out'}},{ti+.38})")
    reps = max(0, int((min(to, DUR) - ti - .6) / 1.3) - 1)
    if reps: js(f"tl.to('#t{i}',{{y:-10,duration:1.3,ease:'sine.inOut',yoyo:true,repeat:{reps}}},{ti+.5})")
    for p in g['pulses']:
        if p['brand'] == it['brand']: js(f"tl.to('#t{i} .ic',{{scale:1.18,duration:.15,yoyo:true,repeat:1,ease:'power2.out'}},{p['t']})")
    if to < DUR: js(f"tl.to('#t{i}',{{autoAlpha:0,scale:.3,y:-260,duration:.35,ease:'power2.in'}},{to})")

# ---- chips with dashed connectors ----
for gi, g in enumerate(TL['groups']):
    c = g.get('chip')
    if not c: continue
    a, b = c['t'], g['t_out']
    H.append(f'<div class="chip" id="c{gi}" style="background:{c["bg"]};color:{c["fg"]}">{c["text"]}</div>')
    js(f"tl.fromTo('#c{gi}',{{autoAlpha:0,scale:.3}},{{autoAlpha:1,scale:1,duration:.4,ease:'back.out(2.5)'}},{a})")
    js(f"tl.to('#c{gi}',{{autoAlpha:0,y:-80,duration:.3}},{b})")
    for i, (tg, it, x, y, s) in enumerate(tiles):
        if tg != gi: continue
        tx = x + (150 if x < 960 else -150); st = max(a, it['t']) + .4
        if st >= b: continue
        H.append(f'<svg class="ln" id="l{i}" width="1920" height="1080"><path d="M960 90 Q {(960+tx)/2} 90 {tx} {y-40}"/></svg>')
        js(f"tl.fromTo('#l{i}',{{autoAlpha:0}},{{autoAlpha:1,duration:.3}},{st})")
        js(f"tl.fromTo('#l{i} path',{{strokeDashoffset:0}},{{strokeDashoffset:-{int((b-st)*120)},duration:{b-st:.2f},ease:'none'}},{st})")
        js(f"tl.to('#l{i}',{{autoAlpha:0,duration:.2}},{b})")

# ---- headline banners (left) ----
for j, bn in enumerate(TL['banners']):
    col = bn.get('color', '#10B981'); fg = '#000' if col.upper() in ('#FACC15', '#FFFFFF', '#FDE047') else '#fff'
    txt = bn['text']
    H.append(f'<div class="ban" id="b{j}"><span class="pill" style="background:{col};color:{fg}">{bn["label"]}</span><div class="bt">{txt}</div></div>')
    js(f"tl.fromTo('#b{j}',{{autoAlpha:0,x:-60}},{{autoAlpha:1,x:0,duration:.35,ease:'power3.out'}},{bn['t_in']})")
    js(f"tl.to('#b{j}',{{autoAlpha:0,x:-60,duration:.25}},{bn['t_out']-.25})")

# ---- summary cards (right) ----
C = TL.get('cards')
if C:
    rnd = random.Random(3); TT = C.get('titles', ['SUMMARY'])
    for k in range(12):
        ts = C['t_in'] + .38 * k
        if ts > C['collapse']: break
        x, y, r = rnd.uniform(1300, 1700), rnd.uniform(140, 760), rnd.uniform(-16, 16)
        lines = ''.join(f'<i style="width:{rnd.randint(45,92)}%"></i>' for _ in range(6))
        H.append(f'<div class="card" id="d{k}" style="left:{x:.0f}px;top:{y:.0f}px;transform:rotate({r:.1f}deg)"><h4>{TT[k%len(TT)]}</h4>{lines}</div>')
        js(f"tl.fromTo('#d{k}',{{autoAlpha:0,scale:.3}},{{autoAlpha:1,scale:1,duration:.35,ease:'back.out(2)'}},{ts:.2f})")
        js(f"tl.to('#d{k}',{{x:{1500-x:.0f},y:{420-y:.0f},scale:.1,rotation:'+=420',autoAlpha:0,duration:.55,ease:'power2.in'}},{C['collapse'] + .1*k:.2f})")
    if C.get('result_title'):
        H.append(f'<div class="gold" id="gold"><div class="star">&#9733;</div><h3>{C["result_title"]}</h3><p>{C.get("result_sub","")}</p></div>')
        js(f"tl.fromTo('#gold',{{autoAlpha:0,scale:.2}},{{autoAlpha:1,scale:1,duration:.5,ease:'back.out(2.2)'}},{C['result_in']})")
        js(f"tl.to('#gold',{{autoAlpha:0,scale:.6,duration:.3}},{C['result_out']})")

# ---- end steps (left) ----
for j, s in enumerate(TL['steps']):
    H.append(f'<div class="step" id="s{j}" style="top:{330 + j*150}px"><span>{j+1}</span>{s["text"]}</div>')
    js(f"tl.fromTo('#s{j}',{{autoAlpha:0,x:-80}},{{autoAlpha:1,x:0,duration:.4,ease:'back.out(2)'}},{s['t']})")

# ---- CTA slams ----
if TL['slams']:
    big = TL.get("cta_big") or KW; bs = min(150, int(560 / max(1, len(big)) * 1.6))
    ss = min(52, int(580 / max(1, len(TL.get("cta_top", "COMMENT"))) * 1.45))
    H.append(f'<div id="cta" style="--bs:{bs}px;--ss:{ss}px"><small>{TL.get("cta_top","COMMENT")}</small><big>{TL.get("cta_big") or KW}</big><em>{TL["cta_line"]}</em></div>')
for a, b in TL['slams']:
    js(f"tl.fromTo('#cta',{{autoAlpha:0,scale:2.2}},{{autoAlpha:1,scale:1,duration:.22,ease:'back.out(1.6)',immediateRender:false}},{a})")
    js(f"tl.fromTo('#flash',{{autoAlpha:.6}},{{autoAlpha:0,duration:.3,immediateRender:false}},{a})")
    js(f"tl.fromTo('#plate',{{x:-18,y:10}},{{x:0,y:0,duration:.45,ease:'elastic.out(1,0.3)',immediateRender:false}},{a})")
    js(f"tl.to('#cta',{{scale:1.04,duration:.3,yoyo:true,repeat:{max(1,int((min(b,DUR)-a-.5)/.6))},ease:'sine.inOut'}},{a+.3})")
    if b < DUR: js(f"tl.to('#cta',{{autoAlpha:0,scale:.5,duration:.25}},{b-.25})")
for z in TL['zooms']:
    js(f"tl.fromTo('#plate',{{scale:1}},{{scale:1.05,duration:.08,ease:'power2.out',yoyo:true,repeat:1,repeatDelay:.25,immediateRender:false}},{z})")

# ---- captions ----
KEYC = {BR[k]['name'].upper().replace(' ', ''): BR[k]['caption'] for k in BR}
def clean(w): return w.upper().replace(',', '').replace('.', '')
def in_cta(t): return any(a <= t < b for a, b in TL['slams'])
chunks, cur = [], []
for i, (s, e, w) in enumerate(words):
    if cur and (len(cur) >= 4 or s - words[cur[-1]][1] > 0.3): chunks.append(cur); cur = []
    cur.append(i)
    if w and w[-1] in '.,?!': chunks.append(cur); cur = []
if cur: chunks.append(cur)
for j, c in enumerate(chunks):
    st = words[c[0]][0]; en = words[c[-1]][1] + .5
    if j + 1 < len(chunks): en = min(en, words[chunks[j + 1][0]][0])
    if in_cta(st): continue
    for a, b in TL['slams']:
        if st < a < en: en = a
    spans = []
    for n, i in enumerate(c):
        tk = clean(words[i][2]); key = tk.strip('?!').replace("'S", '')
        if KW and key == KW: spans.append(f'<span id="w{i}" class="kf">{tk}</span>'); continue
        spans.append(f'<span id="w{i}" style="color:{KEYC.get(key, "#fff")}">{tk}</span>')
        if key not in KEYC:
            nx = words[c[n + 1]][0] if n + 1 < len(c) else en
            js(f"tl.set('#w{i}',{{color:'#FFE14D'}},{words[i][0]});tl.set('#w{i}',{{color:'#fff'}},{nx})")
    H.append(f'<div class="cap" id="k{j}">{" ".join(spans)}</div>')
    js(f"tl.fromTo('#k{j}',{{autoAlpha:0,scale:.85}},{{autoAlpha:1,scale:1,duration:.12,ease:'back.out(3)'}},{st});tl.set('#k{j}',{{autoAlpha:0}},{en})")
H.append('<div id="flash"></div></div>')

CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'youtube.css')).read()
GSAP = os.environ.get('GSAP', 'https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js')
html = f"""<!doctype html><html lang="en" data-resolution="landscape"><head><meta charset="UTF-8"><meta name="viewport" content="width=1920, height=1080">
<script src="{GSAP}"></script><style>{CSS}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}" data-width="1920" data-height="1080" data-fps="30">
{chr(10).join(H)}
</div><script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(J)}
window.__timelines["main"] = tl; tl.seek(0);
</script></body></html>"""
open(os.path.join(PROJ, 'index.html'), 'w').write(html)
print('YT HTML OK', len(html), 'bytes,', len(J), 'tweens')
