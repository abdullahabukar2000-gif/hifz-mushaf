# Where each ayah really is in a whole-surah recording, found by listening.
#
# Some published ayah times are wrong (quran.com's for Khalifa Al-Tunaiji: Yunus
# drifts from about ayah 24, Ar-Ra'd 1-5 point at the wrong audio). This listens
# to the whole surah file with the speech model (in overlapping pieces), then
# walks through the surah ayah by ayah, lining up each ayah's letters with what
# was heard just after the previous ayah. Each ayah starts a moment before its
# first letter is heard; each word likewise. Every ayah is scored (share of its
# letters heard); a surah is only used if every ayah scores well.
#
#   python3 scripts/retime-surah.py <reciter> <part>/<parts>
# Reads the recording addresses from public/data/timings/qdc-<reciter>.json
# (fetch-qdc.py). Writes data/timings-retimed/<reciter>/<surah>.json:
#   {"times": [ayah starts ms..., end], "scores": [...], "words": {"s:a": [[w, start, end], ...]}}

import difflib, glob, json, os, subprocess, sys, tempfile, time, urllib.request
import numpy as np
import onnxruntime as ort

reciter = sys.argv[1]
part, parts = map(int, sys.argv[2].split('/'))
ASSETS = os.environ.get('ALIGN_ASSETS', 'align-assets')
RATE = 16000
CHUNK, OVERLAP = 30.0, 3.0      # seconds heard at a time, and overlap between pieces
LEAD = 0.25                      # an ayah starts this long before its first letter

def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (hifz-mushaf build)'})
            with urllib.request.urlopen(req, timeout=180) as r: return r.read()
        except Exception as e:
            err = e; time.sleep(2 ** i)
    raise err

def decode(data):
    with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
        f.write(data); f.flush()
        raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', f.name, '-ar', str(RATE), '-ac', '1', '-f', 'f32le', '-'],
                             check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

vocab = {int(k): v for k, v in json.load(open(f'{ASSETS}/vocab.json')).items()}
BLANK = 1024
ayah_words = {}
for f in sorted(glob.glob('public/data/pages-*.json')):
    for page in json.load(open(f)).values():
        for line in page['lines']:
            for w in line['words']:
                if w['type'] == 'word': ayah_words.setdefault(w['verseKey'], {})[w['pos']] = w['uthmani']
ayah_words = {k: [v[p] for p in sorted(v)] for k, v in ayah_words.items()}
verses = {c['id']: c['verses_count'] for c in json.load(open('data/chapters.json'))['chapters']}

MARKS = set(chr(c) for c in list(range(0x0610, 0x061B)) + list(range(0x064B, 0x0660)) + [0x0670] + list(range(0x06D6, 0x06EE)) + [0x0640])
UNIFY = {'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ئ': 'ي', 'ؤ': 'و', 'ة': 'ه', 'ۥ': '', 'ۦ': ''}
def letters(text):
    out = []
    for ch in text:
        if ch in MARKS: continue
        ch = UNIFY.get(ch, ch)
        if ch and 'ء' <= ch <= 'ي': out.append(ch)
    return out

opts = ort.SessionOptions()
opts.intra_op_num_threads = os.cpu_count() or 4
model = ort.InferenceSession(f'{ASSETS}/fastconformer_full_mixed.onnx', opts, providers=['CPUExecutionProvider'])

def hear_all(pcm):
    """Every letter heard in the whole file, with its time (s), in order."""
    heard = []
    n, step, size = len(pcm), int((CHUNK - OVERLAP) * RATE), int(CHUNK * RATE)
    start = 0
    while start < n:
        piece = pcm[start:start + size]
        if len(piece) < RATE // 4: break
        out = model.run(None, {'audio_signal': piece[None, :].astype(np.float32), 'length': np.array([len(piece)], dtype=np.int64)})[0][0]
        frame = len(piece) / RATE / out.shape[0]
        # Keep the middle of each piece: from half the overlap in (except the first)
        # to half the overlap before its end (except the last).
        lo = start / RATE + (OVERLAP / 2 if start > 0 else 0)
        hi = (start + size) / RATE - (OVERLAP / 2 if start + size < n else -1)
        prev = -1
        for t, i in enumerate(out.argmax(axis=1)):
            i = int(i)
            if i != prev and i != BLANK:
                at = start / RATE + t * frame
                if lo <= at < hi:
                    for ch in letters(vocab.get(i, '')): heard.append((ch, at))
            prev = i
        start += step
    return heard

def match(want, window):
    """Each wanted letter's index in `window` (or None), using only runs of 3+
    letters in a row (a stray single letter can match anywhere), and the score."""
    sm = difflib.SequenceMatcher(None, want, [c for c, _ in window], autojunk=False)
    at = [None] * len(want)
    for blk in sm.get_matching_blocks():
        if blk.size >= 3 or (blk.size and len(want) <= 6):
            for j in range(blk.size): at[blk.a + j] = blk.b + j
    return at, sum(1 for x in at if x is not None) / len(want)

def place(want, owner, nwords, heard, cursor):
    """Line an ayah's letters up with the heard letters from `cursor`: word starts
    (s), score, new cursor. Moves on only if the ayah was heard well; if not near
    the cursor, looks further ahead."""
    best = None
    for span in (2 * len(want) + 400, 8 * len(want) + 4000):
        window = heard[cursor:cursor + span]
        at, score = match(want, window)
        if best is None or score > best[1]: best = (window, at, score)
        if score >= 0.6: break
    window, at, score = best
    times = [None if x is None else window[x][1] for x in at]
    starts = [None] * nwords
    for k in range(nwords):
        idx = [i for i in range(len(want)) if owner[i] == k and times[i] is not None]
        if idx: starts[k] = times[idx[0]]
    known = [k for k in range(nwords) if starts[k] is not None]
    if not known or score < 0.5: return (None if not known else None), score, cursor
    for k in range(nwords):
        if starts[k] is None:
            before = max([j for j in known if j < k], default=None)
            after = min([j for j in known if j > k], default=None)
            if before is None: starts[k] = starts[after]
            elif after is None: starts[k] = starts[before]
            else: starts[k] = starts[before] + (starts[after] - starts[before]) * (k - before) / (after - before)
    for k in range(1, nwords): starts[k] = max(starts[k], starts[k - 1])
    last = max(x for x in at if x is not None)
    return starts, score, cursor + last + 1

src = json.load(open(f'public/data/timings/qdc-{reciter}.json'))
url_of = lambda s: src['url'].replace('{sss}', f'{s:03d}').replace('{s}', str(s))
weights = [sum(len(ayah_words.get(f'{s}:{a}', [])) for a in range(1, verses[s] + 1)) for s in range(1, 115)]
total, acc, mine = sum(weights), 0, []
for s, w in zip(range(1, 115), weights):
    if int(acc * parts / total) == part - 1: mine.append(s)
    acc += w
if '--only' in sys.argv: mine = [int(x) for x in sys.argv[sys.argv.index('--only') + 1].split(',')]
os.makedirs(f'data/timings-retimed/{reciter}', exist_ok=True)
print(reciter, 'part', part, 'of', parts, 'surahs', mine, flush=True)

for s in mine:
    try: pcm = decode(get(url_of(s)))
    except Exception as e: print(s, 'recording unavailable:', e, flush=True); continue
    heard = hear_all(pcm)
    duration = len(pcm) / RATE
    # What was heard, kept so the lining-up can be checked and tuned without listening again.
    os.makedirs(f'probe/heard/{reciter}', exist_ok=True)
    json.dump({'letters': ''.join(c for c, _ in heard), 'times': [round(t, 2) for _, t in heard], 'duration': duration},
              open(f'probe/heard/{reciter}/{s}.json', 'w'), separators=(',', ':'))
    cursor, times, scores, words_out, word_ends = 0, [], [], {}, []
    for a in range(1, verses[s] + 1):
        key = f'{s}:{a}'
        words = ayah_words[key]
        want, owner = [], []
        for k, w in enumerate(words):
            for ch in letters(w): want.append(ch); owner.append(k)
        starts, score, cursor = place(want, owner, len(words), heard, cursor)
        scores.append(round(score, 3))
        if starts is None:
            times.append(None); words_out[key] = None; continue
        times.append(max(0.0, starts[0] - LEAD))
        words_out[key] = starts
    # Ayah times in ms (each ayah ends where the next starts; the last at the file's end).
    ms = [None if t is None else round(t * 1000) for t in times] + [round(duration * 1000)]
    words_json = {}
    for a in range(1, verses[s] + 1):
        key, st = f'{s}:{a}', words_out[f'{s}:{a}']
        if st is None: continue
        nxt = next((t for t in ms[a:] if t is not None), ms[-1])
        ends = [round(x * 1000) for x in st[1:]] + [nxt]
        words_json[key] = [[i + 1, round(b * 1000), max(round(b * 1000), e)] for i, (b, e) in enumerate(zip(st, ends))]
    old = src.get(str(s))
    shift = [abs(ms[i] - old[i]) for i in range(len(ms) - 1) if old and ms[i] is not None and i < len(old)]
    json.dump({'times': ms, 'scores': scores, 'words': words_json}, open(f'data/timings-retimed/{reciter}/{s}.json', 'w'), separators=(',', ':'))
    low = [f'{s}:{a + 1} ({x})' for a, x in enumerate(scores) if x < 0.8]
    print(f'surah {s}: {len(scores)} ayahs, lowest score {min(scores):.2f}, below 0.8: {low[:12]}{" ..." if len(low) > 12 else ""};'
          f' differs from the published times by up to {max(shift) / 1000 if shift else 0:.1f} s (median {np.median(shift) / 1000 if shift else 0:.2f} s)', flush=True)
