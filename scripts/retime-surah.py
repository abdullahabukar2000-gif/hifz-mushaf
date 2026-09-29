# Where each ayah really is in a whole-surah recording, found by listening.
#
# Some published ayah times are wrong (quran.com's: Khalifa Al-Tunaiji's Yunus
# drifts from about ayah 24; Minshawi's Ar-Ra'd starts most ayahs seconds early,
# so the tail of the ayah before plays first). This listens to the whole surah
# file with the speech model (in overlapping pieces) and checks every published
# ayah start: if the ayah's opening letters are heard right after it, it stays;
# if they're heard later, the ayah starts just before them; if they aren't near
# it at all, the ayah is looked for around there (each ayah on its own, so one
# hard ayah can't throw the others off) and starts where its letters are heard.
#
#   python3 scripts/retime-surah.py <reciter> <part>/<parts>
# Reads the recording addresses from public/data/timings/qdc-<reciter>.json
# (fetch-qdc.py). Writes data/timings-retimed/<reciter>/<surah>.json:
#   {"times": [ayah starts ms..., end], "scores": [...], "words": {"s:a": [[w, start, end], ...]}}

import difflib, glob, json, os, subprocess, sys, tempfile, time, urllib.request
import numpy as np

reciter = sys.argv[1]
part, parts = map(int, sys.argv[2].split('/'))
ASSETS = os.environ.get('ALIGN_ASSETS', 'align-assets')
RATE = 16000
CHUNK, OVERLAP = 30.0, 3.0      # seconds heard at a time, and overlap between pieces
LEAD = 0.25                      # an ayah starts this long before its first letter
# Line up what an earlier run heard (probe/heard/) instead of listening again.
FROM_HEARD = '--from-heard' in sys.argv

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

if not FROM_HEARD:
    import onnxruntime as ort
    vocab = {int(k): v for k, v in json.load(open(f'{ASSETS}/vocab.json')).items()}
    BLANK = 1024
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
    # Letters just before a match that were written a little differently (the
    # mushaf's يَٰٓأَيُّهَا has one alif fewer than "يا أيها"): walk back from each
    # matched letter and take the same letter one or two places earlier.
    heard_letters = [c for c, _ in window]
    for i in range(len(want) - 2, -1, -1):
        if at[i] is None and at[i + 1] is not None:
            for back in (1, 2):
                j = at[i + 1] - back
                if j >= 0 and heard_letters[j] == want[i] and (i == 0 or at[i - 1] is None or at[i - 1] < j):
                    at[i] = j
                    break
    return at, sum(1 for x in at if x is not None) / len(want)

def place(want, owner, nwords, heard, cursor):
    """Line an ayah's letters up with the heard letters from `cursor`: word starts
    (s), score, new cursor. Moves on only if the ayah was heard well; if not near
    the cursor, looks further ahead."""
    best = None
    for span in (2 * len(want) + 400, 8 * len(want) + 4000):
        window = heard[cursor:cursor + span]
        at, score = match(want, window)
        if best is None or score > best[2]: best = (window, at, score)
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

def locate(want, owner, nwords, window):
    """Where an ayah's words start within `window` (heard letters with times): starts (s), score."""
    at, score = match(want, window)
    times = [None if x is None else window[x][1] for x in at]
    starts = [None] * nwords
    for k in range(nwords):
        idx = [i for i in range(len(want)) if owner[i] == k and times[i] is not None]
        if idx: starts[k] = times[idx[0]]
    known = [k for k in range(nwords) if starts[k] is not None]
    if not known: return None, 0.0
    for k in range(nwords):
        if starts[k] is None:
            before = max([j for j in known if j < k], default=None)
            after = min([j for j in known if j > k], default=None)
            if before is None: starts[k] = starts[after]
            elif after is None: starts[k] = starts[before]
            else: starts[k] = starts[before] + (starts[after] - starts[before]) * (k - before) / (after - before)
    for k in range(1, nwords): starts[k] = max(starts[k], starts[k - 1])
    return starts, score

def anchored(s, heard, duration):
    """Each ayah looked for around its published time (a little either side,
    then wider if it isn't there), never before the ayah before it. Each ayah
    is found on its own, so one hard ayah can't throw the rest off."""
    pub = src.get(str(s))
    n = verses[s]
    times, scores, words_out = [], [], {}
    prev_start, prev_end = 0.0, 0.0
    for a in range(1, n + 1):
        key = f'{s}:{a}'
        words = ayah_words[key]
        want, owner = [], []
        for k, w in enumerate(words):
            for ch in letters(w): want.append(ch); owner.append(k)
        if pub and a < len(pub):
            p_from, p_to = pub[a - 1] / 1000, pub[a] / 1000
        else:  # no published time: just after the ayah before, as long as its letters suggest
            p_from, p_to = prev_end, prev_end + len(want) * 0.12
        span = max(1.0, p_to - p_from)
        best = None
        for margin in (8, 30, 120, 600):
            lo = max(prev_start + 0.05, p_from - margin)
            hi = max(p_to + margin, prev_end + 2 * span + margin)
            window = [(c, t) for c, t in heard if lo <= t <= hi]
            if not window: continue
            starts, score = locate(want, owner, len(words), window)
            if starts and (best is None or score > best[1]): best = (starts, score)
            if best and best[1] >= 0.8: break
        if not best or best[1] < 0.3:
            scores.append(round(best[1] if best else 0.0, 3)); times.append(None); words_out[key] = None; continue
        starts, score = best
        scores.append(round(score, 3))
        times.append(max(0.0, starts[0] - LEAD))
        words_out[key] = starts
        prev_start = starts[0]
        # Where this ayah's heard letters end (roughly): its last word's start plus a little.
        prev_end = starts[-1] + 0.3
    return times, scores, words_out

def opening(want, heard, lo, hi):
    """When an ayah's opening letters (`want`, its first few) are heard between
    lo and hi (s): the first of them, or None."""
    near = [(c, t) for c, t in heard if lo <= t <= hi]
    if len(want) < 3 or not near: return None
    sm = difflib.SequenceMatcher(None, want, [c for c, _ in near], autojunk=False)
    m = sm.find_longest_match(0, len(want), 0, len(near))
    if m.size < 3 or m.a > 2: return None
    b = m.b
    for i in range(m.a - 1, -1, -1):          # opening letters just before the match
        for back in (1, 2):
            if b - back >= 0 and near[b - back][0] == want[i]: b -= back; break
    return near[b][1]

def opens_at(want, heard, t):
    """How well the ayah's opening matches what's heard just after t (0-1)."""
    if t is None: return 0.0
    near = [c for c, x in heard if t <= x < t + 3.0][:len(want) + 4]
    return difflib.SequenceMatcher(None, want, near, autojunk=False).ratio() if near else 0.0

def checked(s, heard, found, scores):
    """Keep each published start whose ayah's opening is heard right there;
    change only the others, to a start where the opening clearly is heard:

    - the tail of the ayah before is heard first (published too early): just
      before the opening, found after that tail;
    - a pause, then the opening, within 6 s: just before the opening;
    - the opening was already under way (published too late): up to 5 s back;
    - no published time at all: where listening found the ayah.

    Anything unclear stays as published. Returns the times and the ayahs changed."""
    pub = src.get(str(s))
    n = verses[s]
    out, fixed = [], []
    for a in range(1, n + 1):
        want = [ch for w in ayah_words[f'{s}:{a}'][:2] for ch in letters(w)][:6]
        prev_end = [ch for w in ayah_words[f'{s}:{a - 1}'][-3:] for ch in letters(w)] if a > 1 else []
        before = out[-1] if out and out[-1] is not None else 0.0
        p = pub[a - 1] / 1000 if pub else None
        if p is not None and opens_at(want, heard, p) >= 0.5:
            out.append(p); continue                     # right as published
        candidates = []
        if p is not None:
            # The opening nearest the published start first, then further out.
            st = opening(want, heard, p - 1.5, p + 6.0)
            if st is None: st = opening(want, heard, p - 5.0, p + 30.0)
            if st is not None and st >= p:
                between = [c for c, t in heard if p <= t < st - 0.15]
                tail = difflib.SequenceMatcher(None, between[-12:], prev_end[-12:], autojunk=False).ratio() if prev_end and between else 0
                # Close by, with at most a pause before it; or further on, after the tail of the ayah before.
                if (st <= p + 6.0 and len(between) < 3) or tail >= 0.5: candidates.append(st)
            elif st is not None and p - st <= 5.0 and st > before + 0.5:
                candidates.append(st)
        elif found[a - 1] is not None and scores[a - 1] >= 0.8:
            # No published time: where listening found the ayah.
            f = found[a - 1] + LEAD
            st = opening(want, heard, f - 3.0, f + 6.0)
            if st is not None and st > before + 0.5: candidates.append(st)
        good = [c for c in candidates if opens_at(want, heard, max(0.0, c - 0.05)) >= 0.6]
        if good:
            c = min(good, key=lambda x: abs(x - p) if p is not None else x)
            out.append(max(0.0, c - LEAD)); fixed.append(a)
        else:
            out.append(p if p is not None else found[a - 1])   # can't tell: as published
    for i in range(1, n):                               # never out of order
        if out[i] is None or (out[i - 1] is not None and out[i] < out[i - 1]): out[i] = out[i - 1]
    return out, fixed

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
    if FROM_HEARD:
        try: h = json.load(open(f'probe/heard/{reciter}/{s}.json'))
        except FileNotFoundError: continue
        heard, duration = list(zip(h['letters'], h['times'])), h['duration']
    else:
        try: pcm = decode(get(url_of(s)))
        except Exception as e: print(s, 'recording unavailable:', e, flush=True); continue
        heard = hear_all(pcm)
        duration = len(pcm) / RATE
    # What was heard, kept so the lining-up can be checked and tuned without listening again.
    if not FROM_HEARD: os.makedirs(f'probe/heard/{reciter}', exist_ok=True)
    if not FROM_HEARD:
        json.dump({'letters': ''.join(c for c, _ in heard), 'times': [round(t, 2) for _, t in heard], 'duration': duration},
                  open(f'probe/heard/{reciter}/{s}.json', 'w'), separators=(',', ':'))
    times, scores, words_out = anchored(s, heard, duration)
    times, fixed = checked(s, heard, times, scores)
    # Ayah times in ms (each ayah ends where the next starts; the last at the file's end).
    ms = [round(t * 1000) for t in times] + [round(duration * 1000)]
    # Word times only for the ayahs whose start changed (the others keep theirs).
    words_json = {}
    for a in fixed:
        key, st = f'{s}:{a}', words_out[f'{s}:{a}']
        if st is None: continue
        st = [max(x, ms[a - 1] / 1000 + LEAD) for x in st]
        ends = [round(x * 1000) for x in st[1:]] + [ms[a]]
        words_json[key] = [[i + 1, round(b * 1000), max(round(b * 1000), e)] for i, (b, e) in enumerate(zip(st, ends))]
    json.dump({'times': ms, 'scores': scores, 'fixed': fixed, 'published': bool(src.get(str(s))), 'words': words_json},
              open(f'data/timings-retimed/{reciter}/{s}.json', 'w'), separators=(',', ':'))
    print(f'surah {s}: {len(fixed)} of {len(scores)} ayah starts corrected: {fixed[:20]}{" ..." if len(fixed) > 20 else ""}', flush=True)
