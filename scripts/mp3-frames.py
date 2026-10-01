# Where each moment of a quran.com whole-surah recording sits in its file.
# These files change bit rate as they go, and a browser (iPhone Safari above
# all) can only guess where a time is when it jumps into such a file, landing
# seconds off: an ayah would start with the end of the one before. With this
# map the app fetches the file from the exact frame where the ayah starts, so
# there is nothing to guess (src/recite.ts).
#   python3 scripts/mp3-frames.py <reciter> [surahs]
# Needs public/data/timings/qdc-<reciter>.json (fetch-qdc.py) for the address.
# Writes public/data/frames/<reciter>/<surah>.json:
#   {"first": byte where the audio frames start, "sr": sample rate, "spf": samples per frame,
#    "delay": samples the decoder drops at the start, "f": one character per frame (its size)}
import json, os, sys, time, urllib.request

BITRATES = {1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],      # MPEG-1 layer III
            2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}          # MPEG-2/2.5 layer III
RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}

def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (hifz-mushaf build)'})
            with urllib.request.urlopen(req, timeout=300) as r: return r.read()
        except Exception as e:
            err = e; time.sleep(2 ** i)
    raise err

def frames(d):
    i = 0
    if d[:3] == b'ID3':
        i = 10 + ((d[6] << 21) | (d[7] << 14) | (d[8] << 7) | d[9])
    while i < len(d) - 4 and not (d[i] == 0xFF and d[i + 1] & 0xE0 == 0xE0): i += 1
    first, out, sr, spf, delay, ver = i, [], None, None, 0, None
    while i + 4 <= len(d):
        if not (d[i] == 0xFF and d[i + 1] & 0xE0 == 0xE0): break
        v = (d[i + 1] >> 3) & 3
        br_i, sr_i, pad = d[i + 2] >> 4, (d[i + 2] >> 2) & 3, (d[i + 2] >> 1) & 1
        if br_i in (0, 15) or sr_i == 3: break
        rate = RATES[v][sr_i]
        mpeg1 = v == 3
        size = (144 if mpeg1 else 72) * BITRATES[1 if mpeg1 else 2][br_i] * 1000 // rate + pad
        if sr is None:
            sr, spf, ver = rate, 1152 if mpeg1 else 576, v
            # An info frame (Xing/Info) first: not audio; its LAME tag says how many samples the decoder drops.
            body = d[i:i + size]
            x = max(body.find(b'Xing'), body.find(b'Info'))
            if x >= 0:
                lame = x + 120
                if lame + 24 <= len(body) and body[lame:lame + 4] in (b'LAME', b'Lavf', b'Lavc'):
                    delay = ((body[lame + 21] << 4) | (body[lame + 22] >> 4)) + 529
                else:
                    delay = 529
                i += size; first = i
                continue
        elif v != ver or rate != sr: break
        out.append(chr(48 + br_i * 2 + pad))
        i += size
    return {'first': first, 'sr': sr, 'spf': spf, 'v': ver, 'delay': delay, 'f': ''.join(out), 'bytes': len(d), 'end': i}

reciter = sys.argv[1]
tmpl = json.load(open(f'public/data/timings/qdc-{reciter}.json'))['url']
surahs = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else range(1, 115)
os.makedirs(f'public/data/frames/{reciter}', exist_ok=True)
for s in surahs:
    try:
        d = get(tmpl.replace('{sss}', f'{s:03d}').replace('{s}', str(s)))
    except Exception as e:
        print(reciter, s, 'unavailable:', e, flush=True); continue
    m = frames(d)
    json.dump(m, open(f'public/data/frames/{reciter}/{s}.json', 'w'), separators=(',', ':'))
    print(reciter, s, f"{len(m['f'])} frames, {m['sr']} Hz, delay {m['delay']},"
          f" frames end at byte {m['end']} of {m['bytes']}", flush=True)
