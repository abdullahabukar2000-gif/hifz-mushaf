# Meaning groups for every ayah, worked out automatically.
#
# For each ayah it uses quran.com's word-by-word English (one short gloss per
# Arabic word, from the npm package @kmaslesa/holy-quran-word-by-word-full-data)
# to find which part of The Clear Quran each Arabic word is translated in:
#
#   1. The translation is cut into short pieces at punctuation and at words
#      that start a new clause (and, but, who, when, ...). The pieces are exact
#      slices of the published text; nothing is reworded.
#   2. Each Arabic word goes to the piece whose words best match its gloss
#      (words with no match go with the word after them).
#   3. Pieces are merged until every group is an unbroken run of Arabic words
#      and no two groups' runs overlap. Pieces with no Arabic words join the
#      piece before them.
#
# Merging only ever makes groups bigger, so a doubtful match gives a larger
# block, never a block paired with the wrong words. The hand-checked groups in
# align-source.py (Surah Ibrahim and around it) are kept as they are.
#
#   python3 scripts/align-auto.py <path to data.json of the npm package> --write
#
# Reads data/align/hand.json (from align-source.py) and, with --write, writes
# data/align/clear-quran.json (hand-checked + automatic) and prints how
# closely the automatic groups agree with the hand-checked ones.

import json, glob, os, re, sys

ROOT = os.path.join(os.path.dirname(__file__), '..')
WBW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'node_modules/@kmaslesa/holy-quran-word-by-word-full-data/data.json')

translation = json.load(open(os.path.join(ROOT, 'public/data/clear-quran.json')))

# Arabic word counts from our own pages: groups must match these exactly.
counts = {}
for f in glob.glob(os.path.join(ROOT, 'public/data/pages-*.json')):
    for page in json.load(open(f)).values():
        for line in page['lines']:
            for w in line['words']:
                if w['type'] == 'word':
                    counts[w['verseKey']] = counts.get(w['verseKey'], 0) + 1

glosses = {}
for page in json.load(open(WBW)):
    for a in page['ayahs']:
        for w in a['words']:
            if w['char_type_name'] == 'word':
                glosses.setdefault(w['parentAyahVerseKey'], []).append(w['translation']['text'] or '')

STOP = set('''a an the of to is are was were be been being it its this that these those
he him his she her they them their we us our you your i me my
and or but so then not no nor do does did has have had will shall would should can could may might must
in on at by for from with as into upon over about than there here what which who whom
indeed surely verily certainly truly only very all ever'''.split())

CLAUSE_WORDS = set('''and but so then who whom which whoever whatever when whenever if until while
except unless or yet before after because since though although where lest'''.split())

PREPOSITIONS = set('''in from with to on for by into upon over against among through without about'''.split())
# Where a longer piece may be cut again, and how long "longer" is.
SPLIT_BEFORE = PREPOSITIONS | {'of', 'that', 'the', 'those', 'is', 'are', 'was', 'were', 'will', 'shall', 'has', 'have', 'had'}
LONG = int(os.environ.get('ALIGN_LONG', 3))
SIDE = int(os.environ.get('ALIGN_SIDE', 2))
# How much a word prefers the part of the translation at the same point in the ayah.
POSITION = float(os.environ.get('ALIGN_POSITION', 0.6))
# A stray word joins the group around it if its own group is at least this many times bigger.
STRAY = int(os.environ.get('ALIGN_STRAY', 4))
UNIQUE_ONLY = os.environ.get('ALIGN_UNIQUE', '1') == '1'
# Clues needed to join a group far away (see misplaced()).
FAR_CLUES = int(os.environ.get('ALIGN_FAR', 2))


def norm(word):
    word = word.lower().strip("˹˺()[]“”‘’\"'.,;:!?—-")
    word = word.replace('’', "'")
    for suf in ("'s", 'ing', 'ed', 'es', 's'):
        if len(word) > len(suf) + 2 and word.endswith(suf):
            return word[: -len(suf)]
    return word


def words_of(text):
    """(normalised word, start offset) for each word in text."""
    return [(norm(m.group()), m.start()) for m in re.finditer(r"[^\s—]+", text)]


def content(ws):
    return [w for w in ws if w and w not in STOP and not w.isdigit()]


def same(a, b):
    if a == b:
        return True
    n = min(len(a), len(b))
    return n >= 4 and a[:n] == b[:n] and abs(len(a) - len(b)) <= 3


def cut(text):
    """Split points: after punctuation followed by a space, and before clause words."""
    points = set()
    for m in re.finditer(r'[,;:.!?—][”’]*(?=\s|$)|—', text):
        end = m.end()
        while end < len(text) and text[end] == ' ':
            end += 1
        if 0 < end < len(text):
            points.add(end)
    for m in re.finditer(r'(?<= )(\S+)', text):
        if norm(m.group(1)) in CLAUSE_WORDS and m.group(1)[0].islower():
            # "in which", "from whom": cut before the preposition, not after it.
            before = re.search(r'(\S+) $', text[:m.start()])
            if before and norm(before.group(1)) in PREPOSITIONS:
                points.add(before.start())
            else:
                points.add(m.start())
    # Also before an opening quote.
    for m in re.finditer(r'(?<= )[“‘]', text):
        points.add(m.start())
    points = sorted(points)
    bounds, start = [], 0
    for p in points + [len(text)]:
        if p > start:
            bounds.append([start, p])
            start = p
    # Longer pieces are cut again before a preposition (or "to", "of"), so
    # blocks stay short: a few Arabic words to a few English words.
    finer = []
    for start, end in bounds:
        if len(text[start:end].split()) > LONG:
            piece_start = start
            for m in re.finditer(r'(?<= )(\S+)', text[piece_start:end]):
                at = piece_start + m.start()
                if norm(m.group(1)) in SPLIT_BEFORE and m.group(1)[0].islower() \
                        and len(text[start:at].split()) >= SIDE and len(text[at:end].split()) >= SIDE:
                    finer.append([start, at])
                    start = at
        finer.append([start, end])
    bounds = finer
    # A piece of one word joins the next piece (or the one before, at the end).
    merged = []
    for b in bounds:
        if merged and len(text[merged[-1][0]:merged[-1][1]].split()) < 2:
            merged[-1][1] = b[1]
        else:
            merged.append(b)
    if len(merged) > 1 and len(text[merged[-1][0]:merged[-1][1]].split()) < 2:
        merged[-2][1] = merged[-1][1]
        merged.pop()
    return merged


def align(key):
    text = translation.get(key)
    gl = glosses.get(key)
    n = counts.get(key, 0)
    if not text or not gl or len(gl) != n:
        return None
    pieces = cut(text)
    if len(pieces) < 2 or n < 2:
        return None
    piece_words = [content([w for w, _ in words_of(text[a:b])]) for a, b in pieces]
    mid = [((a + b) / 2) / len(text) for a, b in pieces]

    # 2. Each Arabic word to its best piece.
    home = [None] * n
    for i, g in enumerate(gl):
        gw = content([w for w, _ in words_of(g)])
        if not gw:
            continue
        where = (i + 0.5) / n
        best, best_score = None, 0
        for p, pw in enumerate(piece_words):
            hits = sum(1 for x in gw if any(same(x, y) for y in pw))
            if not hits:
                continue
            score = hits / len(gw) - POSITION * abs(mid[p] - where)
            if score > best_score:
                best, best_score = p, score
        home[i] = best
    if all(h is None for h in home):
        return None
    # Unmatched words: a word with meaning of its own ("remaining") goes with
    # the word before; small words ("indeed", "those who") and words opening
    # with "and", "then", ... go with the word after.
    opens = lambda i: re.match(r'(and|then|so|but|or)\b', gl[i].lower().lstrip('([ '))
    for i in range(1, n):
        if home[i] is None and content([w for w, _ in words_of(gl[i])]) and not opens(i):
            j = i - 1                        # small words just before it come along too
            while j >= 0 and home[j] is None and not content([w for w, _ in words_of(gl[j])]) and not opens(j):
                j -= 1
            if j >= 0 and home[j] is not None:
                for k in range(j + 1, i + 1):
                    home[k] = home[j]
    for i in range(n - 1, -1, -1):
        if home[i] is None and i + 1 < n:
            home[i] = home[i + 1]
    for i in range(n):                       # trailing unmatched: the word before
        if home[i] is None:
            home[i] = home[i - 1]

    # 3. Union pieces until each group is one unbroken run of Arabic words.
    parent = list(range(len(pieces)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    # A piece without Arabic words joins the piece before it, unless it starts
    # a new sentence: then it belongs with what follows.
    has = sorted(set(home))
    for p in range(len(pieces)):
        if p in has:
            continue
        before = [q for q in has if q < p]
        after = [q for q in has if q > p]
        starts = re.match(r'[“‘˹]*[A-Z]', text[pieces[p][0]:])
        parent[p] = after[0] if (starts and after) or not before else before[-1]
    changed = True
    while changed:
        changed = False
        span = {}
        for i, h in enumerate(home):
            r = find(h)
            lo, hi = span.get(r, (i, i))
            span[r] = (min(lo, i), max(hi, i))
        roots = sorted(span, key=lambda r: span[r])
        for a, b in zip(roots, roots[1:]):
            if span[b][0] <= span[a][1]:
                # One stray word is more likely a wrong match than a reason to
                # join two whole pieces: it goes with the group around it.
                in_a = [i for i in range(span[a][0], span[a][1] + 1) if find(home[i]) == b]
                in_b = [i for i in range(span[b][0], span[b][1] + 1) if find(home[i]) == a]
                size_a = sum(1 for h in home if find(h) == a)
                size_b = sum(1 for h in home if find(h) == b)
                if in_a and len(in_a) <= max(1, size_b // STRAY) and size_b > len(in_a):
                    for i in in_a: home[i] = a
                elif in_b and len(in_b) <= max(1, size_a // STRAY) and size_a > len(in_b):
                    for i in in_b: home[i] = b
                else:
                    parent[find(b)] = find(a)
                changed = True
                break
    span = {}
    for i, h in enumerate(home):
        r = find(h)
        lo, hi = span.get(r, (i, i))
        span[r] = (min(lo, i), max(hi, i))
    roots = sorted(span, key=lambda r: span[r])
    if len(roots) < 2:
        return None
    group_of = {r: g for g, r in enumerate(roots)}

    # 4. Check every group: its Arabic glosses and its English must clearly
    #    match. A group that doesn't joins the group next to it in the Arabic.
    gloss_words = [content([w for w, _ in words_of(g)]) for g in gl]
    groups = [[span[r][0], span[r][1], [p for p in range(len(pieces)) if find(p) == r]] for r in roots]
    def hits(words, pool):
        return sum(1 for x in words if any(same(x, y) for y in pool))
    # Words that turn up more than once (Allah, Lord, them...) can't show where
    # anything belongs, so they're left out of this check.
    from collections import Counter
    en_count = Counter(w for pw in piece_words for w in pw)
    ar_count = Counter(w for gw in gloss_words for w in gw)
    def telling(w, counter):
        return not UNIQUE_ONLY or sum(c for x, c in counter.items() if same(x, w)) <= 1
    def misplaced(g):
        """Another group that holds words this group's words clearly belong with, or None.

        A group next to this one needs one such word; a group further away needs
        two (one loose match, like "protecting" and "protector", would otherwise
        join everything in between into one big block).
        """
        lo, hi, ps = groups[g]
        en = [w for p in ps for w in piece_words[p]]
        ar = [w for i in range(lo, hi + 1) for w in gloss_words[i]]
        for h, (lo2, hi2, ps2) in enumerate(groups):
            if h == g:
                continue
            en2 = [w for p in ps2 for w in piece_words[p]]
            ar2 = [w for i in range(lo2, hi2 + 1) for w in gloss_words[i]]
            clues = 0
            # An Arabic word here whose English is only over there...
            for i in range(lo, hi + 1):
                gw = [w for w in gloss_words[i] if telling(w, en_count)]
                if gw and not hits(gw, en) and hits(gw, en2) * 2 >= len(gw):
                    clues += 1
            # ...or an English word here that only translates Arabic over there.
            for y in set(en):
                if telling(y, ar_count) and not hits([y], ar) and hits([y], ar2):
                    clues += 1
            if clues >= (1 if abs(h - g) == 1 else FAR_CLUES):
                return h
        return None
    g = 0
    while g < len(groups) and len(groups) > 1:
        h = misplaced(g)
        if h is None:
            g += 1
            continue
        # Join the two, with every group between them (groups stay unbroken runs).
        a_, b_ = sorted((g, h))
        joined = [groups[a_][0], groups[b_][1], [p for x in groups[a_:b_ + 1] for p in x[2]]]
        groups[a_:b_ + 1] = [joined]
        g = 0
    if len(groups) < 2:
        return None
    group_of = {}
    for gi, (_, _, ps) in enumerate(groups):
        for p in ps:
            group_of[find(p)] = gi
            group_of[p] = gi
    ends = [hi for _, hi, _ in groups]

    # Pieces in English order; neighbours in the same group become one piece.
    out = []
    for p, (a, b) in enumerate(pieces):
        g = group_of[p]
        end = b
        while end > a and text[end - 1] == ' ':
            end -= 1
        if out and out[-1][2] == g:
            out[-1][1] = end
        else:
            out.append([a, end, g])
    return {'ends': ends, 'pieces': out}


def check(key, a):
    n = counts[key]
    ends = a['ends']
    assert ends == sorted(set(ends)) and ends[-1] == n - 1, key
    text = translation[key]
    at = 0
    for s, e, g in a['pieces']:
        assert at <= s < e <= len(text) and 0 <= g < len(ends), key
        assert text[at:s].strip() == '', (key, text[at:s])
        at = e
    assert text[at:].strip() == '', key
    assert set(g for _, _, g in a['pieces']) == set(range(len(ends))), key


out_path = os.path.join(ROOT, 'data/align/clear-quran.json')
existing = json.load(open(os.path.join(ROOT, 'data/align/hand.json')))
hand = existing['verses']

auto = {}
for key in counts:
    a = align(key)
    if a:
        check(key, a)
        auto[key] = a

# How close to the hand-checked groups? (boundary agreement)
tp = fp = fn = 0
for key, h in hand.items():
    a = auto.get(key)
    hb = set(h['ends'][:-1])
    ab = set(a['ends'][:-1]) if a else set()
    tp += len(hb & ab); fp += len(ab - hb); fn += len(hb - ab)
print(f'against the hand-checked ayahs: {tp} breaks agree, {fp} extra, {fn} missed')

verses = {**auto, **hand}
sizes = [len(v['ends']) for v in verses.values()]
print(f'{len(verses)} of {len(counts)} ayahs grouped ({len(counts) - len(verses)} left whole: one piece or no match); '
      f'{sum(sizes)} groups, {sum(sizes) / len(sizes):.1f} per ayah')

existing['verses'] = dict(sorted(verses.items(), key=lambda kv: tuple(map(int, kv[0].split(':')))))
existing['note'] = ('Groups for 13:1-15:15 (all of Ar-Ra'd) checked by hand (scripts/align-source.py); the rest matched automatically '
                    'from quran.com word-by-word glosses (scripts/align-auto.py). Pieces are exact slices of the translation.')
if '--write' in sys.argv:
    json.dump(existing, open(out_path, 'w'), ensure_ascii=False, separators=(',', ':'))
    print('wrote', out_path)
