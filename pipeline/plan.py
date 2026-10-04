"""Turn a word-level transcript + a small per-video job file into a render timeline.

    python3 plan.py words.json job.json timeline.json

Automatic:  brand-logo pops (from brands.json), grouping, pulses on repeat mentions,
            comment-keyword CTA slams, punch-in zooms.
From job:   keyword, CTA sub-line, chips, headline banners, end-steps, summary-cards effect,
            and any manual overrides (extra_mentions, ignore_brands, groups).
"""
import json, re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
HOLD = 6.0          # seconds a group stays up after its last mention
CLUSTER_GAP = 4.0   # mentions closer than this join the same group
MAX_ROW = 5


def norm(tok):
    return re.sub(r"[^a-z0-9.;']", "", tok.lower()).strip(".'")


def lighten(hex_color, amt=0.35):
    h = hex_color.lstrip('#'); r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(c + (255 - c) * amt) for c in (r, g, b))
    return f'#{r:02X}{g:02X}{b:02X}'


def find_mentions(words, brands, ignore):
    toks = [norm(w[2]) for w in words]
    caps = [w[2].strip()[:1].isupper() for w in words]
    table = []  # (n_tokens, alias_tokens, key, cs)
    for key, b in brands.items():
        if key.startswith('_') or key in ignore: continue
        for a in b['aliases']:
            parts = [norm(p) for p in a.split()]
            table.append((len(parts), parts, key, b.get('cs', False)))
    table.sort(key=lambda x: -x[0])  # longest alias first ("claude code" beats "claude")
    out, i = [], 0
    while i < len(toks):
        hit = None
        for n, parts, key, cs in table:
            if toks[i:i + n] == parts and (not cs or caps[i]):
                hit = (n, key); break
        if hit:
            out.append((words[i][0], hit[1], i)); i += hit[0]
        else:
            i += 1
    return out


def find_phrase(words, phrase, t0=0.0, t1=1e9):
    parts = [norm(p) for p in phrase.split()]
    toks = [norm(w[2]) for w in words]
    for i in range(len(toks) - len(parts) + 1):
        if toks[i:i + len(parts)] == parts and t0 <= words[i][0] <= t1:
            return words[i][0]
    return None


def plan(words, job, brands):
    dur = job.get('duration') or (words[-1][1] + 2.0)
    ignore = set(job.get('ignore_brands', []))
    mentions = find_mentions(words, brands, ignore)
    for m in job.get('extra_mentions', []):          # [{"brand":"x","t":12.3}]
        mentions.append((m['t'], m['brand'], -1))
    mentions.sort()

    # 1) cluster mentions by time gap
    clusters = []
    for t, key, _ in mentions:
        if clusters and t - clusters[-1][-1][0] < CLUSTER_GAP:
            clusters[-1].append((t, key))
        else:
            clusters.append([(t, key)])

    # 2) turn clusters into on-screen groups; repeats of on-screen brands become pulses
    groups = []
    for cl in clusters:
        g = groups[-1] if groups else None
        keys = {k for _, k in cl}
        if g and keys <= {it['brand'] for it in g['items']} and cl[0][0] < g['t_out'] + 2.0:
            for t, k in cl: g['pulses'].append({'brand': k, 't': t})
            g['t_out'] = max(g['t_out'], cl[-1][0] + HOLD)
            continue
        items, seen = [], set()
        for t, k in cl:
            if k in seen:
                continue
            seen.add(k); items.append({'brand': k, 't': round(t, 2)})
        for s in range(0, len(items), MAX_ROW):
            chunk = items[s:s + MAX_ROW]
            groups.append({'items': chunk, 't_in': chunk[0]['t'], 't_out': chunk[-1]['t'] + HOLD, 'pulses': []})
    # repeated mention of a brand inside its own cluster -> pulse
    for g in groups:
        first = {it['brand']: it['t'] for it in g['items']}
        for t, k, _ in mentions:
            if k in first and g['t_in'] <= t < g['t_out'] and t > first[k] + 0.5 and \
                    not any(abs(p['t'] - t) < 0.01 for p in g['pulses']):
                g['pulses'].append({'brand': k, 't': round(t, 2)})
    for i, g in enumerate(groups):
        nxt = groups[i + 1]['t_in'] - 0.4 if i + 1 < len(groups) else dur + 1
        for b in job.get('banners', []):            # never overlap a headline that starts later
            if b['t_in'] > g['t_in'] + 1.0: nxt = min(nxt, b['t_in'] - 0.2)
        g['t_out'] = round(min(g['t_out'], nxt), 2)
        n = len(g['items'])
        g['layout'] = 'solo' if n == 1 else 'pair' if n == 2 else 'row'

    # 3) chips: {"text":"MCP","when":"mcp"} attaches to the first pair/solo group whose window contains the phrase
    for c in job.get('chips', []):
        for g in groups:
            if g['layout'] == 'row' or 'chip' in g: continue
            t = find_phrase(words, c['when'], g['t_in'] - 3.0, g['t_out']) if c.get('when') else c.get('t')
            if t is not None and (c.get('when') or g['t_in'] - 3 <= t <= g['t_out']):
                g['chip'] = {'text': c['text'], 't': round(t, 2), 'bg': c.get('bg', '#22D3EE'), 'fg': c.get('fg', '#000000')}
                break

    # 4) CTA slams on every "<keyword>" said after "comment" (or anywhere if comment_required is false)
    kw = job.get('keyword', '').lower()
    slams = []
    if kw:
        for i, w in enumerate(words):
            if norm(w[2]) == kw:
                prev = ' '.join(norm(x[2]) for x in words[max(0, i - 2):i])
                if 'comment' in prev or not job.get('comment_required', True):
                    slams.append(w[0])
    windows = []
    for i, t in enumerate(slams):
        end = dur + 1 if (i == len(slams) - 1 and dur - t < 12) else t + job.get('slam_hold', 3.0)
        if windows and t < windows[-1][1]: windows[-1][1] = max(windows[-1][1], end)
        else: windows.append([round(t, 2), round(end, 2)])

    zooms = sorted({round(g['t_in'], 2) for g in groups} | {w[0] for w in windows} |
                   {b['t_in'] for b in job.get('banners', [])})
    used = {it['brand'] for g in groups for it in g['items']}
    return {
        'duration': round(dur, 3), 'fps': 30,
        'keyword': job.get('keyword', '').upper(), 'cta_line': job.get('cta_line', 'GET THE FREE SKILL'),
        'cta_top': job.get('cta_top', 'COMMENT'),
        'words': words, 'groups': groups, 'slams': windows,
        'banners': job.get('banners', []), 'steps': job.get('steps', []), 'cards': job.get('cards'),
        'zooms': zooms,
        'brands': {k: {**{x: brands[k][x] for x in ('name', 'domain', 'color')}, 'caption': lighten(brands[k]['color'])}
                   for k in used},
    }


if __name__ == '__main__':
    words = [[a, b, w.strip()] for a, b, w in json.load(open(sys.argv[1]))]
    job = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and os.path.exists(sys.argv[2]) else {}
    brands = json.load(open(os.path.join(HERE, '..', 'brands.json')))
    tl = plan(words, job, brands)
    json.dump(tl, open(sys.argv[3] if len(sys.argv) > 3 else 'timeline.json', 'w'), indent=1)
    for g in tl['groups']:
        print(f"{g['t_in']:6.2f}-{g['t_out']:6.2f} {g['layout']:4} " + ', '.join(f"{i['brand']}@{i['t']}" for i in g['items'])
              + (f"  pulses={[p['t'] for p in g['pulses']]}" if g['pulses'] else '') + (f"  chip={g['chip']['text']}@{g['chip']['t']}" if 'chip' in g else ''))
    print('slams', tl['slams'])
