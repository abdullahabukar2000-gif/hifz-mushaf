# Ayah starts and word times for one reciter's surah, from lining up the whole
# surah's text with everything the speech model heard in the recording (letters
# only, in one go, so each ayah can only land after the one before it). Used
# where the ayah-by-ayah check (retime-surah.py) left a start wrong. Needs what
# an earlier retime run heard (probe/heard/<reciter>/<surah>.json); no model.
#   python3 scripts/resync-surah.py <reciter> <surah>[,<surah>...]
# Writes data/timings-retimed/<reciter>/<surah>.json (applied by apply-retimed.py),
# with every ayah's word times.
import difflib, glob, json, os, sys

LEAD = 0.25       # an ayah starts this long before its first letter is heard
MARKS = set(chr(c) for c in list(range(0x0610, 0x061B)) + list(range(0x064B, 0x0660)) + [0x0670] + list(range(0x06D6, 0x06EE)) + [0x0640])
UNIFY = {'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ئ': 'ي', 'ؤ': 'و', 'ة': 'ه', 'ۥ': '', 'ۦ': ''}
def letters(text):
    out = []
    for ch in text:
        if ch in MARKS: continue
        ch = UNIFY.get(ch, ch)
        if ch and 'ء' <= ch <= 'ي': out.append(ch)
    return out

ayah_words = {}
for f in sorted(glob.glob('public/data/pages-*.json')):
    for page in json.load(open(f)).values():
        for line in page['lines']:
            for w in line['words']:
                if w['type'] == 'word': ayah_words.setdefault(w['verseKey'], {})[w['pos']] = w['uthmani']
ayah_words = {k: [v[p] for p in sorted(v)] for k, v in ayah_words.items()}
verses = {c['id']: c['verses_count'] for c in json.load(open('data/chapters.json'))['chapters']}

reciter = sys.argv[1]
for s in map(int, sys.argv[2].split(',')):
    heard = json.load(open(f'probe/heard/{reciter}/{s}.json'))
    got, when, duration = heard['letters'], heard['times'], heard['duration']
    n = verses[s]
    want, owner = [], []                    # every letter of the surah, and its (ayah, word)
    for a in range(1, n + 1):
        for k, w in enumerate(ayah_words[f'{s}:{a}']):
            for ch in letters(w): want.append(ch); owner.append((a, k))
    sm = difflib.SequenceMatcher(None, want, got, autojunk=False)
    at = [None] * len(want)
    for b in sm.get_matching_blocks():
        if b.size >= 2:                     # a lone letter in common says nothing
            for j in range(b.size): at[b.a + j] = when[b.b + j]
    # Each word starts when its first heard letter is; words not heard at all
    # go in between their neighbours.
    starts, word_of = [], {}
    for i, (a, k) in enumerate(owner):
        if (a, k) not in word_of: word_of[(a, k)] = len(starts); starts.append(None)
        if at[i] is not None and starts[word_of[(a, k)]] is None: starts[word_of[(a, k)]] = at[i]
    known = [i for i, x in enumerate(starts) if x is not None]
    for i in range(len(starts)):
        if starts[i] is None:
            lo = max((j for j in known if j < i), default=None)
            hi = min((j for j in known if j > i), default=None)
            if lo is None: starts[i] = starts[hi]
            elif hi is None: starts[i] = starts[lo] + 0.3 * (i - lo)
            else: starts[i] = starts[lo] + (starts[hi] - starts[lo]) * (i - lo) / (hi - lo)
    for i in range(1, len(starts)): starts[i] = max(starts[i], starts[i - 1])
    keys = sorted(word_of, key=word_of.get)
    first = {}                              # ayah -> index of its first word
    for i, (a, k) in enumerate(keys): first.setdefault(a, i)
    times, scores = [], []
    for a in range(1, n + 1):
        times.append(max(0.0, starts[first[a]] - LEAD))
        mine = [i for i, (b, _) in enumerate(owner) if b == a]
        scores.append(round(sum(at[i] is not None for i in mine) / len(mine), 3))
    for a in range(1, n):                   # never before the previous ayah's last letter
        last = max((at[i] for i, (b, _) in enumerate(owner) if b == a and at[i] is not None), default=0)
        times[a] = max(times[a], min(last + 0.1, starts[first[a + 1]]))
    times.append(duration)
    words = {}
    for a in range(1, n + 1):
        idx = [i for i, (b, _) in enumerate(keys) if b == a]
        out = []
        for j, i in enumerate(idx):
            b = starts[i] if j else times[a - 1] + LEAD
            e = starts[idx[j + 1]] if j + 1 < len(idx) else times[a]
            out.append([j + 1, round(b * 1000), round(max(b, e) * 1000)])
        words[f'{s}:{a}'] = out
    src = f'probe/qdc-timings/qdc-{reciter}.json'  # quran.com's, as published
    if not os.path.exists(src): src = f'public/data/timings/qdc-{reciter}.json'
    pub = json.load(open(src)).get(str(s))
    ms = [round(t * 1000) for t in times]
    fixed = [a for a in range(1, n + 1) if not pub or abs(pub[a - 1] - ms[a - 1]) > 400]
    os.makedirs(f'data/timings-retimed/{reciter}', exist_ok=True)
    json.dump({'times': ms, 'scores': scores, 'fixed': fixed, 'published': bool(pub), 'words': words, 'method': 'whole surah'},
              open(f'data/timings-retimed/{reciter}/{s}.json', 'w'), separators=(',', ':'))
    print(f'surah {s}: {len(fixed)} of {n} ayah starts differ from the published ones;'
          f' lowest share of an ayah heard {min(scores)}')
