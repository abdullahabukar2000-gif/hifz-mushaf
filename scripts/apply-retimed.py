# Uses the ayah and word times found by listening (retime-surah.py, committed
# in data/timings-retimed/) in place of the published ones, surah by surah,
# where every ayah was heard well. An ayah the recording doesn't have at all
# (heard hardly at all, at most one per surah) is marked missing: the app says
# so and skips it. Runs at build time after fetch-qdc.py and merge-words.py.
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
    used, refused = [], []
    for f in sorted(glob.glob(f'{d}/*.json'), key=lambda p: int(os.path.basename(p)[:-5])):
        s = os.path.basename(f)[:-5]
        r = json.load(open(f))
        scores, times = r['scores'], r['times']
        absent = [i for i, x in enumerate(scores) if x < ABSENT]
        poor = [i for i, x in enumerate(scores) if ABSENT <= x < GOOD]
        if poor or len(absent) > 1 or any(times[i] is None for i in range(len(scores)) if i not in absent):
            refused.append(s); continue
        # A missing ayah takes no time: it starts where the next one does.
        t = list(times)
        for i in reversed(range(len(scores))):
            if i in absent: t[i] = t[i + 1]
        timing[s] = t
        if absent: missing[s] = [i + 1 for i in absent]
        else: missing.pop(s, None)
        words = {k: v for k, v in r['words'].items() if int(k.split(':')[1]) - 1 not in absent}
        os.makedirs(f'public/data/words/{reciter}', exist_ok=True)
        json.dump({'_base': 'qdc', **words}, open(f'public/data/words/{reciter}/{s}.json', 'w'), separators=(',', ':'))
        used.append(s)
    if missing: timing['missing'] = missing
    json.dump(timing, open(tpath, 'w'), separators=(',', ':'))
    print(reciter, f': ayah times by listening for {len(used)} surahs; kept the published times for {refused or "none"};'
          f' ayahs the recordings lack: {missing or "none"}')
