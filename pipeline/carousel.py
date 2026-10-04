"""Animated Instagram carousel (4:5, 1080x1350) as one HyperFrames composition; run.sh splits it into slides.

    python3 carousel.py carousel.json project_dir/

carousel.json:
  {"handle": "@you", "seconds": 5, "accent": "#FACC15",
   "slides": [ {"type": "logos", "pill": "...", "title": "...", "logos": ["granola", ...], "footer": "Swipe"},
               {"type": "connect", "title": "...", "left": "claude", "right": "chatgpt", "chip": "MCP"},
               {"type": "cards", "pill": "...", "pill_color": "#EF4444", "title": "...", "titles": [...], "result": {"title": "...", "sub": "..."}},
               {"type": "text", "pill": "...", "title": "...", "sub": "...", "logos": ["chatgpt", "claude"]},
               {"type": "cta", "top": "COMMENT", "big": "FILTER", "line": "...", "note": "..."} ]}
Brand logos come from brands.json + logos/<domain>.png (fetched by run.sh).
"""
import json, sys, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
C = json.load(open(sys.argv[1])); PROJ = sys.argv[2]
B = json.load(open(os.path.join(HERE, '..', 'brands.json')))
W, H = 1080, 1350; SEC = C.get('seconds', 5); N = len(C['slides']); DUR = SEC * N
ACC = C.get('accent', '#FACC15'); HANDLE = C.get('handle', '')
html, J = [], []
def js(s): J.append(s)

def logo(key, size, cls='lg', extra=''):
    b = B[key]
    return (f'<div class="{cls}" style="--c:{b["color"]};width:{size}px{extra}"><div class="ic" style="width:{size}px;height:{size}px;border-radius:{size*.24}px">'
            f'<img src="logos/{b["domain"]}.png"></div><div class="lab" style="font-size:{max(22, size*.15):.0f}px">{b["name"]}</div></div>')

for i, s in enumerate(C['slides']):
    t0 = i * SEC; sid = f's{i}'; T = s.get('type', 'text')
    inner = [f'<div class="hdr"><span>{HANDLE}</span><span>{i+1}/{N}</span></div>']
    if s.get('pill'):
        inner.append(f'<div class="pill" style="background:{s.get("pill_color", ACC)};color:{"#000" if s.get("pill_color", ACC).upper() in ("#FACC15","#FFFFFF","#FDE047") else "#fff"}">{s["pill"]}</div>')
    if s.get('title'): inner.append(f'<h1 class="title">{s["title"]}</h1>')
    if s.get('sub'): inner.append(f'<p class="sub">{s["sub"]}</p>')
    if T == 'logos':
        n = len(s['logos']); size = 190 if n > 3 else 240
        cols = 3 if n > 4 else n
        inner.append('<div class="grid">' + ''.join(logo(k, size) for k in s['logos']) + '</div>')
    elif T == 'connect':
        inner.append('<div class="pair">' + logo(s['left'], 270) + logo(s['right'], 270) + '</div>')
        inner.append(f'<svg class="wire" width="{W}" height="{H}"><path d="M 300 905 Q 540 1150 780 905"/></svg>')
        inner.append(f'<div class="chip">{s.get("chip","")}</div>')
    elif T == 'cards':
        rnd = random.Random(i); s['_cards'] = []
        for k, ct in enumerate(s.get('titles', ['SUMMARY'] * 8)):
            x, y, r = rnd.uniform(140, 720), rnd.uniform(560, 880), rnd.uniform(-14, 14)
            lines = ''.join(f'<i style="width:{rnd.randint(45, 92)}%"></i>' for _ in range(6))
            inner.append(f'<div class="card" id="{sid}c{k}" style="left:{x:.0f}px;top:{y:.0f}px"><h4>{ct}</h4>{lines}</div>')
            s['_cards'].append((x, y, r))
        if s.get('result'):
            inner.append(f'<div class="gold"><div class="star">&#9733;</div><h3>{s["result"]["title"]}</h3><p>{s["result"].get("sub","")}</p></div>')
    elif T == 'text' and s.get('logos'):
        inner.append('<div class="row">' + ''.join(logo(k, 230) for k in s['logos']) + '</div>')
    elif T == 'cta':
        inner.append(f'<div class="bubble"><small>{s.get("top","COMMENT")}</small><big>{s["big"]}</big><em>{s.get("line","")}</em></div>')
        if s.get('note'): inner.append(f'<p class="note">{s["note"]}</p>')
    if s.get('footer'): inner.append(f'<div class="swipe">{s["footer"]} <b>&rarr;</b></div>')
    html.append(f'<section id="{sid}" class="clip slide" data-start="{t0}" data-duration="{SEC}" data-track-index="{i % 2}">' + ''.join(inner) + '</section>')

    # ---- animation per slide (all tweens absolute on the master timeline) ----
    q = lambda sel: f"'#{sid} {sel}'"
    js(f"tl.fromTo({q('.hdr')},{{autoAlpha:0}},{{autoAlpha:1,duration:.4}},{t0})")
    js(f"tl.fromTo({q('.pill')},{{autoAlpha:0,y:-30,scale:.6}},{{autoAlpha:1,y:0,scale:1,duration:.4,ease:'back.out(2.5)'}},{t0+.1})")
    js(f"tl.fromTo({q('.title')},{{autoAlpha:0,y:50}},{{autoAlpha:1,y:0,duration:.55,ease:'power3.out'}},{t0+.25})")
    js(f"tl.fromTo({q('.sub')},{{autoAlpha:0,y:30}},{{autoAlpha:1,y:0,duration:.5,ease:'power3.out'}},{t0+.55})")
    if T in ('logos', 'connect') or (T == 'text' and s.get('logos')):
        js(f"tl.fromTo({q('.lg')},{{autoAlpha:0,scale:.2,y:160,rotation:-18}},{{autoAlpha:1,scale:1,y:0,rotation:0,duration:.55,ease:'back.out(1.8)',stagger:.28}},{t0+.7})")
        js(f"tl.to({q('.lg')},{{y:-10,duration:1.1,ease:'sine.inOut',yoyo:true,repeat:1,stagger:.15}},{t0+2.4})")
    if T == 'connect':
        js(f"tl.fromTo({q('.wire')},{{autoAlpha:0}},{{autoAlpha:1,duration:.3}},{t0+1.5})")
        js(f"tl.fromTo({q('.wire path')},{{strokeDashoffset:0}},{{strokeDashoffset:-400,duration:{SEC-1.5},ease:'none'}},{t0+1.5})")
        js(f"tl.fromTo({q('.chip')},{{autoAlpha:0,scale:.3}},{{autoAlpha:1,scale:1,duration:.45,ease:'back.out(2.5)'}},{t0+1.6})")
    if T == 'cards':
        for k, (x, y, r) in enumerate(s['_cards']):
            js(f"tl.fromTo('#{sid}c{k}',{{autoAlpha:0,scale:.3,rotation:0}},{{autoAlpha:1,scale:1,rotation:{r:.1f},duration:.35,ease:'back.out(2)'}},{t0+.7+.18*k:.2f})")
        if s.get('result'):
            t1 = t0 + .7 + .18 * len(s['_cards']) + .3
            for k, (x, y, r) in enumerate(s['_cards']):
                js(f"tl.to('#{sid}c{k}',{{x:{445-x:.0f},y:{760-y:.0f},scale:.1,rotation:{r+420:.0f},autoAlpha:0,duration:.5,ease:'power2.in'}},{t1+.06*k:.2f})")
            s['_t2'] = t1 + .06 * len(s['_cards']) + .4
            js(f"tl.fromTo({q('.gold')},{{autoAlpha:0,scale:.2}},{{autoAlpha:1,scale:1,duration:.55,ease:'back.out(2.2)'}},{s['_t2']:.2f})")
            js(f"tl.to({q('.gold')},{{scale:1.05,duration:.5,yoyo:true,repeat:1,ease:'sine.inOut'}},{s['_t2']+.8:.2f})")
        else:
            js(f"tl.to({q('.card')},{{y:'+=10',duration:.9,yoyo:true,repeat:1,ease:'sine.inOut',stagger:.05}},{t0+3.0})")
    if T == 'cta':
        js(f"tl.fromTo({q('.bubble')},{{autoAlpha:0,scale:2.2}},{{autoAlpha:1,scale:1,duration:.3,ease:'back.out(1.6)'}},{t0+.6})")
        js(f"tl.fromTo('#flash',{{autoAlpha:.55}},{{autoAlpha:0,duration:.35,immediateRender:false}},{t0+.6})")
        js(f"tl.to({q('.bubble')},{{scale:1.04,duration:.4,yoyo:true,repeat:{max(1, int((SEC-1.2)/.4)-1)},ease:'sine.inOut'}},{t0+1.1})")
        js(f"tl.fromTo({q('.note')},{{autoAlpha:0,y:30}},{{autoAlpha:1,y:0,duration:.45}},{t0+1.2})")
    if s.get('footer'):
        js(f"tl.fromTo({q('.swipe')},{{autoAlpha:0,x:-30}},{{autoAlpha:1,x:0,duration:.4}},{t0+1.8})")
        js(f"tl.to({q('.swipe b')},{{x:14,duration:.35,yoyo:true,repeat:5,ease:'sine.inOut'}},{t0+2.3})")

CSS = open(os.path.join(HERE, 'carousel.css')).read().replace('ACC', ACC)
GSAP = os.environ.get('GSAP', 'https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js')
doc = f"""<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width={W}, height={H}">
<script src="{GSAP}"></script><style>{CSS}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}" data-width="{W}" data-height="{H}" data-fps="30">
<div class="bg"></div>
{chr(10).join(html)}
<div id="flash"></div>
</div><script>
const tl = gsap.timeline({{ paused: true }});
tl.fromTo('.bg',{{backgroundPosition:'0px 0px'}},{{backgroundPosition:'0px 240px',duration:{DUR},ease:'none'}},0);
{chr(10).join(J)}
window.__timelines["main"] = tl; tl.seek(0);
</script></body></html>"""
open(os.path.join(PROJ, 'index.html'), 'w').write(doc)
print('CAROUSEL HTML OK', N, 'slides,', DUR, 's')
