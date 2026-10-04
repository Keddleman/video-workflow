"""Make sure every brand in the timeline has a usable logo image.
python3 icons.py timeline.json logos/
Site icons smaller than 64px (or missing) are replaced with a generated tile: a chat bubble for
brands marked "icon": "chat", otherwise the brand's initials on its colour."""
import sys, json, os
from PIL import Image, ImageDraw, ImageFont
TL = json.load(open(sys.argv[1])); D = sys.argv[2]
FONT = os.environ.get('FONT', '/usr/share/fonts/truetype/higgsfield/Montserrat-ExtraBold.ttf')
def hexc(h): h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
for k, b in TL['brands'].items():
    p = f"{D}/{b['domain']}.png"
    try:
        ok = Image.open(p).size[0] >= 64
    except Exception:
        ok = False
    if ok: continue
    S = 256; im = Image.new('RGBA', (S, S), hexc(b['color']) + (255,)); d = ImageDraw.Draw(im)
    if b.get('icon') == 'chat':
        d.rounded_rectangle([40, 52, 216, 178], 48, fill=(255, 255, 255, 255))
        d.polygon([(78, 168), (62, 214), (124, 172)], fill=(255, 255, 255, 255))
        for x in (88, 128, 168): d.ellipse([x - 13, 102, x + 13, 128], fill=hexc(b['color']) + (255,))
    else:
        ini = ''.join(w[0] for w in b['name'].split())[:2].upper() or b['name'][:2].upper()
        d.text((S / 2, S / 2), ini, font=ImageFont.truetype(FONT, 120 if len(ini) == 1 else 104), fill=(255, 255, 255, 255), anchor='mm')
    im.save(p); print('generated icon for', b['name'])
