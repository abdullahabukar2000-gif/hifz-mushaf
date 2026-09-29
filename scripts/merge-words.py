# Puts together, per reciter and surah, the word timings the app uses:
# quran.com's (fetched by fetch-qdc.py into public/data/words/) and the ones
# found by listening to the recordings (align-words.py, committed in
# data/words-aligned/). quran.com's come first; an ayah it doesn't have is
# taken from the listening, if that matched with confidence.
# Writes public/data/words/<reciter>/<surah>.json with "_base" saying which
# recording the times are in ("qdc", "sufi" or "everyayah").
#   python3 scripts/merge-words.py
import glob, json, os

MIN_SCORE = float(os.environ.get('WORDS_MIN_SCORE', '-1.5'))
used = kept_out = 0
for path in sorted(glob.glob('data/words-aligned/*/*.json')):
    reciter, surah = path.split('/')[-2], path.split('/')[-1][:-5]
    aligned = json.load(open(path))
    base = aligned.pop('_base', 'everyayah')
    scores = aligned.pop('_scores', {})
    out_path = f'public/data/words/{reciter}/{surah}.json'
    qdc = {}
    if os.path.exists(out_path):
        qdc = {k: v for k, v in json.load(open(out_path)).items() if not k.startswith('_')}
    if base == 'qdc' and not os.path.exists(f'public/data/timings/qdc-{reciter}.json'):
        continue  # the app isn't playing those recordings: the times wouldn't fit
    merged = dict(qdc) if base == 'qdc' else {}
    for key, words in aligned.items():
        if key in merged: continue
        if scores.get(key, -99) < MIN_SCORE: kept_out += 1; continue
        merged[key] = words
        used += 1
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump({'_base': base, **merged}, open(out_path, 'w'), separators=(',', ':'))
print(f'word timings from listening: {used} ayahs used, {kept_out} left to estimate (not confident)')
