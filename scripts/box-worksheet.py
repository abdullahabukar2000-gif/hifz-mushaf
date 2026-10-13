# Worksheet for making a surah's meaning boxes by hand (the surah-boxes skill):
# for each ayah, The Clear Quran's translation, then the mushaf's Arabic words
# by index with quran.com's word-by-word gloss beside each, and the current boxes.
#   python3 scripts/box-worksheet.py <surah> [path to the word-by-word data.json]
# The gloss data is the npm package @kmaslesa/holy-quran-word-by-word-full-data
# (`npm pack` it into the scratchpad if node_modules doesn't have it).
import glob, json, os, sys

ROOT = os.path.join(os.path.dirname(__file__), '..')
s = int(sys.argv[1])
WBW = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'node_modules/@kmaslesa/holy-quran-word-by-word-full-data/data.json')
words = {}
for f in glob.glob(os.path.join(ROOT, 'data/pages/*.json')):
    for l in json.load(open(f))['lines']:
        for w in l['words']:
            if w['type'] == 'word' and w['verseKey'].startswith(f'{s}:'):
                words.setdefault(w['verseKey'], {})[w['pos']] = w.get('uthmani') or w.get('text')
gloss = {}
for page in json.load(open(WBW)):
    for a in page['ayahs']:
        for w in a['words']:
            if w['char_type_name'] == 'word' and w['parentAyahVerseKey'].startswith(f'{s}:'):
                gloss.setdefault(w['parentAyahVerseKey'], []).append(w['translation']['text'] or '')
tr = {}
for f in glob.glob(os.path.join(ROOT, 'data/translations/clear-quran/*.json')): tr.update(json.load(open(f))['verses'])
boxes = json.load(open(os.path.join(ROOT, 'data/align/clear-quran.json')))['verses']
for a in sorted(words, key=lambda k: int(k.split(':')[1])):
    ws = [words[a][p] for p in sorted(words[a])]
    g = gloss.get(a, [])
    print(f'\n{a}  ({len(ws)} words)\n  EN: {tr[a]}')
    if len(g) != len(ws): print(f'  !! {len(g)} glosses for {len(ws)} words: line them up by meaning, not by position')
    for i, w in enumerate(ws): print(f'  {i:3} {w}  — {g[i] if i < len(g) else "?"}')
    b = boxes.get(a)
    if b: print('  now:', ' | '.join(f'…{e}: ' + ' '.join(tr[a][x:y] for x, y, gi in b['pieces'] if gi == n) for n, e in enumerate(b['ends'])))
