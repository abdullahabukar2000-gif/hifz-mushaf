# Uses the ayah starts checked by listening (retime-surah.py, committed in
# data/timings-retimed/) in place of quran.com's published ones. Where a surah
# has published times, each start was kept if the ayah's opening is heard
# there, or moved to where it is heard: every surah is applied. A surah with
# no published times is applied only if every ayah was heard well; an ayah the
# recording doesn't have at all (heard hardly at all, at most one per surah) is
# marked missing: the app says so and skips it.
# Word times of moved ayahs replace those in the words file (the rest stay).
# Runs at build time after fetch-qdc.py and merge-words.py.
#   python3 scripts/apply-retimed.py
import glob, json, os

GOOD, ABSENT = 0.8, 0.3
for d in sorted(glob.glob('data/timings-retimed/*')):
    reciter = os.path.basename(d)
    tpath = f'public/data/timings/qdc-{reciter}.json'
    if not os.path.exists(tpath):
        print(reciter, ': no quran.com recordings in this build — skipped'); continue
    timing = json.load(open(tpath))
    missing = timing.get('missing', {})
    used, refused, moved = [], [], 0
    for f in sorted(glob.glob(f'{d}/*.json'), key=lambda p: int(os.path.basename(p)[:-5])):
        s = os.path.basename(f)[:-5]
        r = json.load(open(f))
        scores, times = r['scores'], r['times']
        absent = []
        if not r.get('published'):
            absent = [i for i, x in enumerate(scores) if x < ABSENT]
            # "by_hand": ayahs whose start was checked by hand (see the file's note).
            poor = [i for i, x in enumerate(scores) if ABSENT <= x < GOOD and str(i + 1) not in r.get('by_hand', {})]
            if poor or len(absent) > 1:
                refused.append(s); continue
        if any(times[i] is None for i in range(len(times)) if i not in absent):
            refused.append(s); continue
        # A missing ayah takes no time: it starts where the next one does.
        t = list(times)
        for i in reversed(range(len(scores))):
            if i in absent: t[i] = t[i + 1]
        timing[s] = t
        if absent: missing[s] = [i + 1 for i in absent]
        elif not r.get('published'): missing.pop(s, None)
        wpath = f'public/data/words/{reciter}/{s}.json'
        words = json.load(open(wpath)) if os.path.exists(wpath) else {}
        if words.get('_base', 'qdc') != 'qdc': words = {}
        for i in absent: words.pop(f'{s}:{i + 1}', None)
        words.update({k: v for k, v in r.get('words', {}).items() if int(k.split(':')[1]) - 1 not in absent})
        words['_base'] = 'qdc'
        os.makedirs(os.path.dirname(wpath), exist_ok=True)
        json.dump(words, open(wpath, 'w'), separators=(',', ':'))
        used.append(s); moved += len(r.get('fixed', []))
    if missing: timing['missing'] = missing
    json.dump(timing, open(tpath, 'w'), separators=(',', ':'))
    print(reciter, f': ayah starts checked by listening in {len(used)} surahs ({moved} moved);'
          f' kept the published times for {refused or "none"}; ayahs the recordings lack: {missing or "none"}')
