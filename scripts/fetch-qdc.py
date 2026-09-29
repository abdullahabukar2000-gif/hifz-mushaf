# Word-by-word timings from quran.com's player (api.qurancdn.com), for the
# reciters whose recordings it has. Each reciter's surah recordings come with
# the time every ayah starts and every word starts and ends in that file, so
# the app plays those same files and can light up each word as it's recited.
#
# Writes, per reciter (app id):
#   public/data/timings/qdc-<id>.json  {"url": "https://…/{s}.mp3", "<surah>": [ayah starts (ms)…, end]}
#   public/data/words/<id>/<surah>.json  {"<s>:<a>": [[word, start ms, end ms], …]}
# Checks every surah: ayahs in order, word numbers matching the mushaf's words.
# A reciter that doesn't check out is left out (the app then keeps using its
# per-ayah recordings, with estimated word timings), and the build carries on.
#   python3 scripts/fetch-qdc.py
import glob, json, os, re, sys, time, urllib.request

WANT = {  # app id: (name contains, style must contain / must not contain)
    'alafasy': ('afasy', 'murattal', None),
    'husary': ('husary', 'murattal', 'muallim'),
    'minshawi': ('minshawi', 'murattal', 'mujawwad'),
}
API = 'https://api.qurancdn.com/api/qdc/audio/reciters'

def get(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (hifz-mushaf build)', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())
        except Exception as e:
            err = e; time.sleep(2 ** attempt)
    raise err

words = {}
for f in glob.glob('public/data/pages-*.json'):
    for p in json.load(open(f)).values():
        for l in p['lines']:
            for w in l['words']:
                if w['type'] == 'word': words[w['verseKey']] = words.get(w['verseKey'], 0) + 1
counts = {c['id']: c['verses_count'] for c in json.load(open('data/chapters.json'))['chapters']}

try:
    reciters = get(f'{API}?locale=en')['reciters']
except Exception as e:
    print('reciter list unavailable:', e); sys.exit(0)
for r in reciters: print('qdc reciter', r.get('id'), r.get('name'), json.dumps(r.get('style')))

def style_of(r):
    s = r.get('style')
    return str(s.get('name') if isinstance(s, dict) else s or '')

def segs_of(v, start):
    """Word timings as [[word, start, end]], absolute in the file."""
    out = []
    for s in v.get('segments') or []:
        s = [x for x in s if isinstance(x, (int, float))]
        if len(s) == 4: w, a, b = s[1], s[2], s[3]      # [from word, to word, start, end]
        elif len(s) == 3: w, a, b = s                    # [word, start, end]
        else: continue
        out.append([int(w), int(a), int(b)])
    # Relative to the ayah? Then shift into the file.
    if out and start > 1000 and out[0][1] < start - 500: out = [[w, a + start, b + start] for w, a, b in out]
    return out

def one(app, name, style, avoid):
        cand = [r for r in reciters if name in (r.get('name') or '').lower()]
        cand = [r for r in cand if style in style_of(r).lower()] or cand
        if avoid: cand = [r for r in cand if avoid not in (style_of(r) + ' ' + (r.get('name') or '')).lower()]
        if not cand: print(app, ': not on quran.com'); return
        rid = cand[0]['id']
        print(app, '->', rid, cand[0].get('name'), style_of(cand[0]))
        timing, per_surah, url_tmpl, problems, word_ok, word_all = {}, {}, None, [], 0, 0
        for s in range(1, 115):
            try: af = get(f'{API}/{rid}/audio_files?chapter={s}&segments=true')['audio_files'][0]
            except Exception as e: problems.append(f'{s}: {e}'); break
            url = af.get('audio_url') or ''
            t = re.sub(r'(?<=/)0*%d(?=\.mp3$)' % s, '{s}' if not re.search(r'/0\d', url) else '{sss}', url)
            if url_tmpl is None: url_tmpl = t
            elif t != url_tmpl: problems.append(f'{s}: file address {url} doesn\'t follow {url_tmpl}'); break
            vt = sorted(af.get('verse_timings') or [], key=lambda v: int(v['verse_key'].split(':')[1]))
            if len(vt) != counts[s]: problems.append(f'{s}: {len(vt)} ayah timings for {counts[s]} ayahs'); break
            starts = [int(v['timestamp_from']) for v in vt]
            if starts != sorted(starts): problems.append(f'{s}: ayahs out of order'); break
            timing[str(s)] = starts + [int(vt[-1]['timestamp_to'])]
            ws = {}
            for v in vt:
                seg = segs_of(v, int(v['timestamp_from']))
                n = words.get(v['verse_key'], 0)
                word_all += 1
                # Usable: word numbers within the ayah and in order, times in order. A
            # word missing from the list just shows with the next one (or when the
            # ayah ends).
            ws_ = [w for w, _, _ in seg]
            if seg and ws_ == sorted(ws_) and 1 <= ws_[0] and ws_[-1] <= n and [a for _, a, _ in seg] == sorted(a for _, a, _ in seg):
                    word_ok += 1
                    ws[v['verse_key']] = seg
            per_surah[s] = ws
            if s in (1, 14): print(app, s, url, json.dumps(vt[0])[:400])
        if problems or not url_tmpl:
            print(app, ': left out —', problems[:5]); return
        print(app, f': usable word timings for {word_ok} of {word_all} ayahs (the rest: estimated)')
        if word_ok < 0.8 * word_all:
            print(app, ': too many ayahs whose word timings don\'t match — left out'); return
        os.makedirs('public/data/timings', exist_ok=True)
        json.dump({'url': url_tmpl, **timing}, open(f'public/data/timings/qdc-{app}.json', 'w'), separators=(',', ':'))
        os.makedirs(f'public/data/words/{app}', exist_ok=True)
        for s, ws in per_surah.items():
            json.dump(ws, open(f'public/data/words/{app}/{s}.json', 'w'), separators=(',', ':'))
        print(app, ': written')

for app, (name, style, avoid) in WANT.items():
    try: one(app, name, style, avoid)
    except Exception as e: print(app, ': left out —', repr(e))
