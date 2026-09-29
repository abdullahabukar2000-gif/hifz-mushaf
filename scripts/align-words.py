# Word timings for reciters that have none published, found by listening to
# their recordings: an open Quran speech model (Tilawi's FastConformer,
# CC-BY-4.0) hears each ayah, and the letters it hears are lined up with the
# ayah's own words (harakat and tajweed marks set aside on both sides), so each
# word starts when its first letter is heard, in the very file the app plays.
# Nothing is guessed from word lengths; each ayah gets a score (the share of its
# letters heard), and one heard too poorly is left out (the app then estimates
# for that ayah only). The report says how many.
#
# Runs on GitHub Actions (the model and the recordings aren't reachable here):
#   python3 scripts/align-words.py <reciter> <part>/<parts> [--missing-only]
# Writes data/words-aligned/<reciter>/<surah>.json:
#   {"_base": "qdc" | "sufi" | "everyayah", "_scores": {...}, "<s>:<a>": [[word, start ms, end ms], ...]}
# where times are in the surah file (qdc, sufi) or in the ayah's own file
# (everyayah).

import difflib, glob, json, os, subprocess, sys, tempfile, time, urllib.request
import numpy as np
import onnxruntime as ort

reciter = sys.argv[1]
part, parts = map(int, sys.argv[2].split('/'))
missing_only = '--missing-only' in sys.argv
ASSETS = os.environ.get('ALIGN_ASSETS', 'align-assets')
RATE = 16000
# Share of the ayah's letters heard (0-1): kept for every ayah (in "_scores"),
# so the cut-off can be chosen afterwards (scripts/merge-words.py); only
# hopeless matches are dropped here.
MIN_SCORE = float(os.environ.get('ALIGN_MIN_SCORE', '0.4'))

EVERYAYAH = {'muaiqly': 'MaherAlMuaiqly128kbps', 'ayyub': 'Muhammad_Ayyoub_128kbps', 'tunaiji': 'khalefa_al_tunaiji_64kbps'}
# Where everyayah's numbering is off: the file that holds each ayah (see src/recite.ts FILE_FIXES).
FILE_FIXES = {('tunaiji', 14): lambda a: None if a == 1 else (a - 1 if a <= 51 else 52)}

def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (hifz-mushaf build)'})
            with urllib.request.urlopen(req, timeout=120) as r: return r.read()
        except Exception as e:
            err = e; time.sleep(2 ** i)
    raise err

def decode(data):
    with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
        f.write(data); f.flush()
        raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', f.name, '-ar', str(RATE), '-ac', '1', '-f', 'f32le', '-'],
                             check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

# ---------------------------------------------------------------- text
vocab = {int(k): v for k, v in json.load(open(f'{ASSETS}/vocab.json')).items()}
BLANK = 1024
# The ayah's words: the app's own mushaf text (so the words are exactly the ones on screen).
ayah_words = {}
for f in sorted(glob.glob('public/data/pages-*.json')):
    for page in json.load(open(f)).values():
        for line in page['lines']:
            for w in line['words']:
                if w['type'] == 'word': ayah_words.setdefault(w['verseKey'], {})[w['pos']] = w['uthmani']
ayah_words = {k: [v[p] for p in sorted(v)] for k, v in ayah_words.items()}
verses = {c['id']: c['verses_count'] for c in json.load(open('data/chapters.json'))['chapters']}

# Letters only: harakat, tajweed marks and small signs dropped, letter forms
# unified, so what the model writes (with or without harakat) and the mushaf's
# spelling compare letter for letter.
MARKS = set(chr(c) for c in list(range(0x0610, 0x061B)) + list(range(0x064B, 0x0660)) + [0x0670] + list(range(0x06D6, 0x06EE)) + [0x0640])
UNIFY = {'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ئ': 'ي', 'ؤ': 'و', 'ة': 'ه', 'ۥ': '', 'ۦ': ''}
def letters(text):
    out = []
    for ch in text:
        if ch in MARKS: continue
        ch = UNIFY.get(ch, ch)
        if ch and 'ء' <= ch <= 'ي': out.append(ch)
    return out

# ---------------------------------------------------------------- model
opts = ort.SessionOptions()
opts.intra_op_num_threads = os.cpu_count() or 4
model = ort.InferenceSession(f'{ASSETS}/fastconformer_full_mixed.onnx', opts, providers=['CPUExecutionProvider'])

def hear(pcm):
    """What the model hears: its letters, each with the frame it was first heard, and the frame length (s)."""
    out = model.run(None, {'audio_signal': pcm[None, :].astype(np.float32), 'length': np.array([len(pcm)], dtype=np.int64)})[0][0]
    best = out.argmax(axis=1)
    heard, prev = [], -1
    for t, i in enumerate(best):
        i = int(i)
        if i != prev and i != BLANK:
            for ch in letters(vocab.get(i, '')): heard.append((ch, t))
        prev = i
    return heard, len(pcm) / RATE / len(best)

shown = 0

def align_ayah(pcm, words):
    """When each word starts and ends (s), and the share of the ayah's letters heard (0-1)."""
    global shown
    heard, frame = hear(pcm)
    want, owner = [], []
    for k, w in enumerate(words):
        for ch in letters(w): want.append(ch); owner.append(k)
    if shown < 3:
        shown += 1
        print('  heard:   ', ''.join(c for c, _ in heard), '\n  expected:', ''.join(want), flush=True)
    if not want or not heard: return None, 0.0
    sm = difflib.SequenceMatcher(None, want, [c for c, _ in heard], autojunk=False)
    at = [None] * len(want)                   # frame each expected letter was heard at
    for blk in sm.get_matching_blocks():
        for j in range(blk.size): at[blk.a + j] = heard[blk.b + j][1]
    score = sum(1 for x in at if x is not None) / len(want)
    # A word starts when its first heard letter was heard (its letters before that were missed).
    starts = [None] * len(words)
    for k in range(len(words)):
        idx = [i for i in range(len(want)) if owner[i] == k and at[i] is not None]
        if idx: starts[k] = at[idx[0]] - (idx[0] - owner.index(k))  # back up a frame per missed letter
    # Words not heard at all: in between their neighbours.
    known = [k for k in range(len(words)) if starts[k] is not None]
    if not known: return None, 0.0
    for k in range(len(words)):
        if starts[k] is None:
            before = max([j for j in known if j < k], default=None)
            after = min([j for j in known if j > k], default=None)
            if before is None: starts[k] = starts[after] - (after - k)
            elif after is None: starts[k] = starts[before] + (k - before)
            else: starts[k] = starts[before] + (starts[after] - starts[before]) * (k - before) / (after - before)
    for k in range(1, len(words)):           # never going backwards
        starts[k] = max(starts[k], starts[k - 1])
    total = len(pcm) / RATE
    out = []
    for k in range(len(words)):
        b = max(0.0, starts[k] * frame)
        e = starts[k + 1] * frame if k + 1 < len(words) else min(total, (max(x for x in at if x is not None) + 2) * frame)
        out.append([b, max(b, e)])
    return out, score

# ---------------------------------------------------------------- audio
def surah_source(s):
    """(base, whole-surah url, ayah times) for reciters played from one file per surah, else None."""
    if reciter == 'sufi':
        t = json.load(open('public/data/timings/abdurrashid_sufi.json')).get(str(s))
        return ('sufi', f'https://download.quranicaudio.com/quran/abdurrashid_sufi/{s:03d}.mp3', t) if t else None
    path = f'public/data/timings/qdc-{reciter}.json'
    if os.path.exists(path):
        d = json.load(open(path))
        t = d.get(str(s))
        if t: return ('qdc', d['url'].replace('{sss}', f'{s:03d}').replace('{s}', str(s)), t)
    return None

# Split the Quran into parts of about the same number of words.
weights = [sum(len(ayah_words.get(f'{s}:{a}', [])) for a in range(1, verses[s] + 1)) for s in range(1, 115)]
total, acc, mine = sum(weights), 0, []
for s, w in zip(range(1, 115), weights):
    if int(acc * parts / total) == part - 1: mine.append(s)
    acc += w
if '--only' in sys.argv:  # a quick check on a few surahs: --only 1,20
    mine = [int(x) for x in sys.argv[sys.argv.index('--only') + 1].split(',')]
LIMIT = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 10**9
print(reciter, 'part', part, 'of', parts, 'surahs', mine[0], '-', mine[-1], flush=True)

stats = {'aligned': 0, 'low': 0, 'mismatch': 0, 'nofile': 0, 'skipped': 0}
scores = []
out_dir = f'data/words-aligned/{reciter}'
os.makedirs(out_dir, exist_ok=True)
for s in mine:
    src = surah_source(s)
    base = src[0] if src else 'everyayah'
    have = {}
    if missing_only:
        try: have = json.load(open(f'public/data/words/{reciter}/{s}.json'))
        except Exception: have = {}
    result = {'_base': base, '_scores': {}}
    surah_pcm = None
    for a in range(1, min(verses[s], LIMIT) + 1):
        key = f'{s}:{a}'
        if key in have: stats['skipped'] += 1; continue
        words = ayah_words.get(key)
        if not words: stats['mismatch'] += 1; continue
        try:
            if src:
                if surah_pcm is None: surah_pcm = decode(get(src[1]))
                times = src[2]
                start = max(0, times[a - 1] / 1000 - 0.35)
                end = (times[a] / 1000 + 0.35) if a < len(times) else len(surah_pcm) / RATE
                pcm = surah_pcm[int(start * RATE):int(end * RATE)]
                offset = start
            else:
                fa = FILE_FIXES.get((reciter, s), lambda x: x)(a)
                if fa is None: stats['nofile'] += 1; continue
                pcm = decode(get(f'https://everyayah.com/data/{EVERYAYAH[reciter]}/{s:03d}{fa:03d}.mp3'))
                offset = 0
        except Exception as e:
            print(key, 'audio unavailable:', e, flush=True); stats['nofile'] += 1; continue
        got, score = align_ayah(pcm, words)
        best = (got, score) if got else None
        if not best or best[1] < MIN_SCORE:
            stats['low'] += 1
            print(key, 'not confident', round(best[1], 2) if best else None, flush=True)
            continue
        scores.append(best[1])
        result['_scores'][key] = round(float(best[1]), 3)
        result[key] = [[i + 1, round((offset + b) * 1000), round((offset + e) * 1000)] for i, (b, e) in enumerate(best[0])]
        stats['aligned'] += 1
    json.dump(result, open(f'{out_dir}/{s}.json', 'w'), separators=(',', ':'))
    print(f'surah {s}: done', stats, flush=True)
if scores:
    q = np.percentile(scores, [5, 50, 95])
    print('scores 5/50/95%:', [round(x, 3) for x in q])
print('FINAL', reciter, part, stats)
