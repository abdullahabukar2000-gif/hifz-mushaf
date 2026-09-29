# Word timings for reciters that have none published, found by listening to
# their recordings: an open Quran speech model (Tilawi's FastConformer,
# CC-BY-4.0) hears each ayah, and the ayah's known words are lined up against
# what it hears (CTC forced alignment). That gives the time each word starts
# and ends in the very file the app plays. Nothing is guessed from word
# lengths; an ayah that doesn't line up with confidence is left out (the app
# then estimates for that ayah only), and the report says how many.
#
# Runs on GitHub Actions (scripts need the model and the recordings):
#   python3 scripts/align-words.py <reciter> <part>/<parts> [--missing-only]
# Writes data/words-aligned/<reciter>/<surah>.json:
#   {"_base": "qdc" | "sufi" | "everyayah", "<s>:<a>": [[word, start ms, end ms], ...]}
# where times are in the surah file (qdc, sufi) or in the ayah's own file
# (everyayah).

import glob, json, os, subprocess, sys, tempfile, time, urllib.request
import numpy as np
import onnxruntime as ort

reciter = sys.argv[1]
part, parts = map(int, sys.argv[2].split('/'))
missing_only = '--missing-only' in sys.argv
ASSETS = os.environ.get('ALIGN_ASSETS', 'align-assets')
RATE = 16000
# Mean log-prob per frame along the matched path: kept for every ayah (in
# "_scores"), so the cut-off can be chosen afterwards (scripts/merge-words.py);
# only hopeless matches are dropped here.
MIN_SCORE = float(os.environ.get('ALIGN_MIN_SCORE', '-4'))

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
# Keyed "surah:ayah:ayah" (a range of one ayah).
tokens = {k.rsplit(':', 1)[0]: v for k, v in json.load(open(f'{ASSETS}/quran_ctc_tokens.json')).items() if k.split(':')[1] == k.split(':')[2]}
counts = {}
for f in glob.glob('public/data/pages-*.json'):
    for page in json.load(open(f)).values():
        for line in page['lines']:
            for w in line['words']:
                if w['type'] == 'word': counts[w['verseKey']] = counts.get(w['verseKey'], 0) + 1
verses = {c['id']: c['verses_count'] for c in json.load(open('data/chapters.json'))['chapters']}

def words_of(ids):
    """Token ids grouped into words (a new word starts at a piece beginning with ▁).
    Every token is kept: the model hears each one."""
    words = []
    for i in ids:
        if vocab.get(i, '').startswith('\u2581') or not words: words.append([])
        words[-1].append(i)
    return words

BASMALAH = words_of(tokens['1:1'])

# ---------------------------------------------------------------- model
opts = ort.SessionOptions()
opts.intra_op_num_threads = os.cpu_count() or 4
model = ort.InferenceSession(f'{ASSETS}/fastconformer_full_mixed.onnx', opts, providers=['CPUExecutionProvider'])

def logprobs(pcm):
    out = model.run(None, {'audio_signal': pcm[None, :].astype(np.float32), 'length': np.array([len(pcm)], dtype=np.int64)})[0][0]
    return out  # [T, vocab]

def force_align(lp, labels):
    """CTC Viterbi: the frame span of each label, and the path's mean log-prob per frame."""
    T, L = lp.shape[0], len(labels)
    S = 2 * L + 1
    lab = np.full(S, BLANK); lab[1::2] = labels
    skip = np.zeros(S, dtype=bool)
    skip[3::2] = np.array(labels[1:]) != np.array(labels[:-1])
    if T < L: return None, -99
    NEG = -1e30
    alpha = np.full(S, NEG); alpha[0] = lp[0, BLANK]; alpha[1] = lp[0, lab[1]]
    back = np.zeros((T, S), dtype=np.int8)
    for t in range(1, T):
        a0 = alpha
        a1 = np.concatenate(([NEG], alpha[:-1]))
        a2 = np.where(skip, np.concatenate(([NEG, NEG], alpha[:-2])), NEG)
        stack = np.stack([a0, a1, a2])
        choice = np.argmax(stack, axis=0)
        alpha = stack[choice, np.arange(S)] + lp[t, lab]
        back[t] = choice
    end = S - 1 if alpha[S - 1] >= alpha[S - 2] else S - 2
    score = alpha[end] / T
    spans = [[None, None] for _ in range(L)]
    s = end
    for t in range(T - 1, -1, -1):
        if s % 2 == 1:
            k = s // 2
            spans[k][1] = t if spans[k][1] is None else spans[k][1]
            spans[k][0] = t
        s -= back[t, s]
    return spans, score

def align_ayah(pcm, words):
    """[[start s, end s] per word] or None, and the score."""
    labels = [i for w in words for i in w]
    lp = logprobs(pcm)
    spans, score = force_align(lp, labels)
    if spans is None or any(a is None for a, _ in spans): return None, score
    frame = len(pcm) / RATE / lp.shape[0]
    out, k = [], 0
    for w in words:
        first, last = spans[k], spans[k + len(w) - 1]
        out.append([first[0] * frame, (last[1] + 1) * frame])
        k += len(w)
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
weights = [sum(counts.get(f'{s}:{a}', 0) for a in range(1, verses[s] + 1)) for s in range(1, 115)]
total, acc, mine = sum(weights), 0, []
for s, w in zip(range(1, 115), weights):
    if int(acc * parts / total) == part - 1: mine.append(s)
    acc += w
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
    for a in range(1, verses[s] + 1):
        key = f'{s}:{a}'
        if key in have: stats['skipped'] += 1; continue
        words = words_of(tokens.get(key, []))
        if len(words) != counts.get(key):
            stats['mismatch'] += 1; continue
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
        best = None
        variants = [words] + ([BASMALAH + words] if a == 1 and s not in (1, 9) else [])
        for v in variants:
            got, score = align_ayah(pcm, v)
            if got and (best is None or score > best[1]): best = (got[len(v) - len(words):], score)
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
