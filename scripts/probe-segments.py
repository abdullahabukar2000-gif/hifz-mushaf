"""Which reciters have published word-by-word timings, and for which audio files?
Run on GitHub Actions (the sites aren't reachable from the dev sandbox); the
report is committed to probe/segments.txt."""
import json, urllib.request, re

out = []
def get(url, raw=False):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 hifz-mushaf probe', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return body.decode('utf-8', 'replace') if raw else json.loads(body)
    except Exception as e:
        return f'ERR {e}'

out.append('== QDC reciters (quran.com player)')
lst = get('https://api.qurancdn.com/api/qdc/audio/reciters?locale=en')
recs = lst.get('reciters', []) if isinstance(lst, dict) else []
if not recs: out.append(str(lst)[:500])
for r in recs:
    rid = r.get('id')
    af = get(f'https://api.qurancdn.com/api/qdc/audio/reciters/{rid}/audio_files?chapter=14&segments=true')
    line = f"{rid} | {r.get('name')} | {(r.get('style') or {}).get('name') if isinstance(r.get('style'), dict) else r.get('style')}"
    if isinstance(af, dict) and af.get('audio_files'):
        f = af['audio_files'][0]
        vt = f.get('verse_timings') or []
        seg = vt[0].get('segments') if vt else None
        line += f" | url={f.get('audio_url')} | verses={len(vt)} | 14:1 segs={json.dumps(seg)[:160] if seg else None}"
        if vt: line += f" | 14:1 from={vt[0].get('timestamp_from')} to={vt[0].get('timestamp_to')}"
    else:
        line += f' | {str(af)[:150]}'
    out.append(line)

out.append('\n== quran.com v4 recitations (per-ayah files)')
lst = get('https://api.quran.com/api/v4/resources/recitations')
for r in (lst.get('recitations', []) if isinstance(lst, dict) else []):
    rid = r.get('id')
    a = get(f'https://api.quran.com/api/v4/recitations/{rid}/by_ayah/14:1')
    line = f"{rid} | {r.get('reciter_name')} | {r.get('style')}"
    if isinstance(a, dict) and a.get('audio_files'):
        f = a['audio_files'][0]
        line += f" | url={f.get('url')} | segs={json.dumps(f.get('segments'))[:160]}"
    else:
        line += f' | {str(a)[:150]}'
    out.append(line)

out.append('\n== QUL recitations page')
html = get('https://qul.tarteel.ai/resources/recitation', raw=True)
out.append(str(len(html)) + ' chars')
names = re.findall(r'<h\d[^>]*>([^<]{3,80})</h\d>', html) if not html.startswith('ERR') else []
out.append(' ; '.join(n.strip() for n in names[:200]))
links = sorted(set(re.findall(r'href="(/resources/recitation/\d+)"', html)))
out.append(' '.join(links[:300]))
for l in links[:3]:
    p = get('https://qul.tarteel.ai' + l, raw=True)
    out.append(f'-- {l}: ' + re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', p))[:1500])

open('probe/segments.txt', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out)[:5000])
