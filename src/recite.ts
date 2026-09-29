// Recitation: plays a range of ayahs by one reciter, one recording per ayah,
// with repeats and speed, and saves surahs for offline only when asked.
//
// Recordings are everyayah.com's per-ayah MP3s (one file per ayah, named
// SSSAAA.mp3), with its quranicaudio.com mirror as a second address. They're
// played straight from the web unless the surah has been downloaded, in which
// case the saved copy plays and no connection is needed.

import { getChapter } from './data';

export interface Reciter {
  id: string;
  name: string;
  /** everyayah.com folders: one file per ayah. */
  folders: string[];
  /**
   * Or one file per surah, with the time each ayah starts (from the Quran
   * Android app's timing database, fetched at build time by
   * scripts/fetch-timings.py).
   */
  gapless?: { base: string; timings: string };
  /**
   * quran.com's recordings of this reciter, with a time for every word
   * (scripts/fetch-qdc.py, at build time). When they're there, they're played
   * instead, so each word can be revealed as it's recited; if not, the
   * per-ayah recordings above are used.
   */
  qdc?: boolean;
}

export const RECITERS: Reciter[] = [
  { id: 'alafasy', name: 'Mishary Alafasy', folders: ['Alafasy_128kbps', 'Alafasy_64kbps'], qdc: true },
  { id: 'husary', name: 'Mahmoud Khalil Al-Husary', folders: ['Husary_128kbps', 'Husary_64kbps'], qdc: true },
  { id: 'minshawi', name: 'Muhammad Siddiq Al-Minshawi', folders: ['Minshawy_Murattal_128kbps'], qdc: true },
  { id: 'muaiqly', name: 'Maher Al-Muaiqly', folders: ['MaherAlMuaiqly128kbps', 'Maher_AlMuaiqly_64kbps'] },
  { id: 'tunaiji', name: 'Khalifa Al-Tunaiji', folders: ['khalefa_al_tunaiji_64kbps'], qdc: true },
  { id: 'ayyub', name: 'Muhammad Ayyub', folders: ['Muhammad_Ayyoub_128kbps', 'Muhammad_Ayyoub_64kbps'] },
  {
    id: 'sufi', name: 'Abdirashid Ali Sufi', folders: [],
    gapless: { base: 'https://download.quranicaudio.com/quran/abdurrashid_sufi/', timings: 'data/timings/abdurrashid_sufi.json' },
  },
];

const HOSTS = ['https://everyayah.com/data/', 'https://mirrors.quranicaudio.com/everyayah/'];
const SAVED = 'hifz-recitations-v1';

const store = {
  get(key: string) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* private mode */ } },
};

export const reciterById = (id: string) => RECITERS.find((r) => r.id === id) ?? RECITERS[0];
const file = (surah: number, ayah: number) => `${String(surah).padStart(3, '0')}${String(ayah).padStart(3, '0')}.mp3`;

/**
 * Where the source's numbering is off, the file that really holds each ayah
 * (null: the source has no recording of it). Found by comparing every file's
 * length with the ayah lengths and with other reciters (scripts/check-audio*.py).
 * Khalifa Al-Tunaiji, Surah Ibrahim: files 1-50 hold ayahs 2-51, file 51
 * repeats ayah 51, file 52 is ayah 52, and ayah 1 is missing.
 */
const FILE_FIXES: Record<string, Record<number, (ayah: number) => number | null>> = {
  tunaiji: { 14: (a) => (a === 1 ? null : a <= 51 ? a - 1 : 52) },
};
// (Only for the per-ayah files: quran.com's whole-surah recordings are timed by ayah.)
const fileAyah = (r: Reciter, surah: number, ayah: number): number | null =>
  qdcFiles.has(r.id) ? ayah : FILE_FIXES[r.id]?.[surah]?.(ayah) ?? ayah;
/** How many ayahs of a surah this reciter's source actually has. */
const recordedCount = (r: Reciter, surah: number) => {
  const n = getChapter(surah)?.verses_count ?? 0;
  let c = 0;
  for (let a = 1; a <= n; a++) if (fileAyah(r, surah, a) !== null) c++;
  return c;
};

// Saved copies made before a fix above hold the wrong ayahs: clear them once.
(async () => {
  try {
    if (localStorage.getItem('recite-fixes') === '1' || !('caches' in window)) return;
    const cache = await caches.open('hifz-recitations-v1');
    for (const req of await cache.keys()) if (/__recitation\/tunaiji\/014/.test(req.url)) await cache.delete(req);
    localStorage.setItem('recite-fixes', '1');
  } catch { /* try again next time */ }
})();

// ------------------------------------------------------------------ one file per surah

const timingJobs = new Map<string, Promise<Record<string, number[]>>>();
/** quran.com recordings found for a reciter: the address of each surah's file. */
const qdcFiles = new Map<string, string>();
const timingsUrl = (r: Reciter) => (r.gapless ? r.gapless.timings : `data/timings/qdc-${r.id}.json`);
/** Ayah start times (ms) per surah, with the surah's end time last. */
function timings(r: Reciter): Promise<Record<string, number[]>> {
  let job = timingJobs.get(r.id);
  if (!job) {
    job = fetch(timingsUrl(r)).then(async (res) => {
      if (!res.ok) throw new Error();
      const t = await res.json();
      if (typeof t.url === 'string') { qdcFiles.set(r.id, t.url); delete t.url; }
      return t;
    });
    job.catch(() => { if (!r.qdc) timingJobs.delete(r.id); });
    timingJobs.set(r.id, job);
  }
  return job;
}
// Find out straight away which reciters have quran.com's word-timed recordings.
const qdcChecks = new Map<string, Promise<boolean>>();
for (const r of RECITERS.filter((x) => x.qdc)) qdcChecks.set(r.id, timings(r).then(() => true, () => false));
/** Plays one file per surah (with ayah times), rather than one per ayah. */
const wholeSurah = (r: Reciter) => !!r.gapless || qdcFiles.has(r.id);
async function settled(r: Reciter): Promise<void> { await qdcChecks.get(r.id); }

const wordJobs = new Map<string, Promise<Record<string, [number, number, number][]>>>();
/** When each word starts and ends (ms, in the surah file), if known. */
function wordTimes(r: Reciter, surah: number): Promise<Record<string, [number, number, number][]>> | null {
  if (!qdcFiles.has(r.id)) return null;
  const k = `${r.id}/${surah}`;
  let job = wordJobs.get(k);
  if (!job) {
    job = fetch(`data/words/${r.id}/${surah}.json`).then((res) => { if (!res.ok) throw new Error(); return res.json(); });
    job.catch(() => wordJobs.delete(k));
    wordJobs.set(k, job);
  }
  return job;
}
const loadedWords = new Map<string, Record<string, [number, number, number][]>>();

/**
 * Where an ayah sits in a one-file-per-surah recording: which surah's file,
 * and its start and end in seconds. The basmalah is what comes before ayah 1
 * in the surah's own file, or else Al-Fatihah's first ayah.
 */
async function segment(r: Reciter, surah: number, ayah: number, basmalah: boolean): Promise<{ file: number; from: number; to: number } | null> {
  const t = await timings(r);
  const times = t[surah];
  if (!times) return null;
  if (basmalah) {
    if (times[0] > 2500) return { file: surah, from: 0, to: times[0] / 1000 };
    const f = t[1];
    return f ? { file: 1, from: f[0] / 1000, to: f[1] / 1000 } : null;
  }
  const from = times[ayah - 1];
  const to = times[ayah] ?? Infinity;
  return from === undefined ? null : { file: surah, from: from / 1000, to: to / 1000 };
}

const surahFile = (surah: number) => `${String(surah).padStart(3, '0')}.mp3`;
const surahUrl = (r: Reciter, surah: number) => {
  const t = qdcFiles.get(r.id);
  if (t) return t.replace('{sss}', String(surah).padStart(3, '0')).replace('{s}', String(surah));
  return r.gapless!.base + surahFile(surah);
};

/** Web addresses to try for one ayah, the one that worked last time first. */
function addresses(r: Reciter, surah: number, ayah: number): string[] {
  if (wholeSurah(r)) return [surahUrl(r, surah)];
  const real = fileAyah(r, surah, ayah);
  if (real === null) return [];
  ayah = real;
  const all = HOSTS.flatMap((host) => r.folders.map((folder) => `${host}${folder}/`));
  const good = store.get(`recite-base-${r.id}`);
  if (good && all.includes(good)) all.splice(all.indexOf(good), 1), all.unshift(good);
  return all.map((base) => base + file(surah, ayah));
}
const rememberBase = (r: Reciter, url: string) => store.set(`recite-base-${r.id}`, url.slice(0, url.lastIndexOf('/') + 1));

/** The key a saved recording is kept under, whichever address it came from. */
const savedKey = (r: Reciter, surah: number, ayah: number) =>
  new Request(`${location.origin}/__recitation/${r.id}${qdcFiles.has(r.id) ? '-qdc' : ''}/${wholeSurah(r) ? surahFile(surah) : file(surah, ayah)}`);

async function savedBlob(r: Reciter, surah: number, ayah: number): Promise<Blob | null> {
  if (!('caches' in window)) return null;
  try {
    const res = await (await caches.open(SAVED)).match(savedKey(r, surah, ayah));
    return res ? await res.blob() : null;
  } catch { return null; }
}

// ------------------------------------------------------------------ downloads

export interface SurahDownload { reciter: string; surah: number; saved: number; total: number; bytes: number }

/** Every surah with any saved recordings, per reciter. */
export async function listDownloads(): Promise<SurahDownload[]> {
  if (!('caches' in window)) return [];
  const cache = await caches.open(SAVED);
  const found = new Map<string, SurahDownload>();
  for (const req of await cache.keys()) {
    const m = req.url.match(/__recitation\/([^/]+)\/(\d{3})(\d{3})?\.mp3$/);
    if (!m) continue;
    const surah = Number(m[2]);
    const id = `${m[1].replace(/-qdc$/, '')}:${surah}`;
    // A whole-surah file counts as the whole surah.
    const entry = found.get(id) ?? { reciter: m[1].replace(/-qdc$/, ''), surah, saved: 0, total: m[3] ? recordedCount(reciterById(m[1].replace(/-qdc$/, '')), surah) : 1, bytes: 0 };
    entry.saved++;
    const res = await cache.match(req);
    entry.bytes += Number(res?.headers.get('content-length')) || 0;
    found.set(id, entry);
  }
  // The basmalah is kept as Al-Fatihah's first ayah; alone, it isn't a download of Al-Fatihah.
  for (const [id, d] of found) if (d.surah === 1 && d.saved === 1 && d.total > 1) found.delete(id);
  return [...found.values()].sort((a, b) => a.surah - b.surah || a.reciter.localeCompare(b.reciter));
}

const downloading = new Map<string, { done: number; total: number; stop: boolean }>();
export const downloadProgress = (reciter: string, surah: number) => downloading.get(`${reciter}:${surah}`);

/**
 * Save a whole surah by one reciter for offline listening. Reports progress as
 * it goes; already-saved ayahs are skipped. Resolves with an error message, or
 * null when every ayah is saved.
 */
export async function downloadSurah(reciterId: string, surah: number, progress: (done: number, total: number) => void): Promise<string | null> {
  if (!('caches' in window)) return 'This browser can’t save recordings.';
  const r = reciterById(reciterId);
  await settled(r);
  const total = getChapter(surah)?.verses_count ?? 0;
  const job = { done: 0, total, stop: false };
  downloading.set(`${r.id}:${surah}`, job);
  try { await navigator.storage?.persist?.(); } catch { /* optional */ }
  const cache = await caches.open(SAVED);
  // Surahs after the first open with the basmalah, recited from Al-Fatihah's first ayah.
  const needsBasmalah = surah !== 1 && surah !== 9;
  let list: [number, number][] = [...(needsBasmalah ? [[1, 1] as [number, number]] : []),
    ...Array.from({ length: total }, (_, i) => [surah, i + 1] as [number, number])];
  if (wholeSurah(r)) {
    // One file for the surah (and Al-Fatihah's, if the basmalah comes from there).
    const b = needsBasmalah ? await segment(r, surah, 1, true).catch(() => null) : null;
    list = [[surah, 1], ...(b && b.file === 1 ? [[1, 1] as [number, number]] : [])];
    job.total = 1;
  }
  let failed = '';
  for (let i = 0; i < list.length && !job.stop; i += 4) {
    await Promise.all(list.slice(i, i + 4).map(async ([s, a]) => {
      const key = savedKey(r, s, a);
      if (fileAyah(r, s, a) !== null && !(await cache.match(key))) {
        let saved = false;
        for (const url of addresses(r, s, a)) {
          try {
            const res = await fetch(url, { mode: 'cors' });
            if (!res.ok) continue;
            const blob = await res.blob();
            await cache.put(key, new Response(blob, { headers: { 'content-type': 'audio/mpeg', 'content-length': String(blob.size) } }));
            rememberBase(r, url);
            saved = true;
            break;
          } catch { /* next address */ }
        }
        if (!saved) failed = navigator.onLine ? 'Some ayahs couldn’t be downloaded from this reciter’s source.' : 'You’re offline. Connect to download.';
      }
      if (s === surah) { job.done++; progress(job.done, job.total); }
    }));
    if (failed) break;
  }
  downloading.delete(`${r.id}:${surah}`);
  return job.stop ? 'Stopped.' : failed || null;
}

export function stopDownload(reciterId: string, surah: number): void {
  const job = downloading.get(`${reciterId}:${surah}`);
  if (job) job.stop = true;
}

export async function deleteDownload(reciterId: string, surah: number): Promise<void> {
  const cache = await caches.open(SAVED);
  for (const req of await cache.keys()) {
    const n = String(surah).padStart(3, '0');
    if (req.url.includes(`/__recitation/${reciterId}/${n}`) || req.url.includes(`/__recitation/${reciterId}-qdc/${n}`)) await cache.delete(req);
  }
}

// ------------------------------------------------------------------ playing

export interface PlayPlan {
  reciter: string;
  /** First and last ayah, as [surah, ayah]; the range may run across surahs. */
  from: [number, number];
  to: [number, number];
  /** Times each ayah is recited in a row; 0 = keep repeating. */
  eachAyah: number;
  /** Times the whole range is played; 0 = keep repeating. */
  wholeRange: number;
  speed: number;
  /** Seconds of quiet after each recitation, to recite it back yourself. */
  pause: number;
}

export interface NowPlaying { plan: PlayPlan; surah: number; ayah: number; ayahRound: number; rangeRound: number; basmalah: boolean; playing: boolean }

type Listener = (now: NowPlaying | null, error?: string) => void;
const listeners = new Set<Listener>();
export function onPlayer(fn: Listener): () => void { listeners.add(fn); return () => listeners.delete(fn); }

const audio = new Audio();
audio.preload = 'auto';
let now: NowPlaying | null = null;
let blobUrl: string | null = null;
let pauseTimer: number | undefined;
let token = 0;
/** For one-file-per-surah reciters: where the current ayah ends (seconds). */
let segmentEnd: number | null = null;
/** Set between one recitation finishing and the next starting. */
let between = false;
/** The recording runs straight on into the next ayah (no jump needed). */
let continuing = false;
/** For one-file-per-surah reciters: where the current ayah starts (seconds). */
let segmentStart = 0;

/**
 * How far through the current ayah the recitation is (0 to 1), several times
 * a second; and, where the reciter's word timings are known, how many of the
 * ayah's words have been started.
 */
type ProgressFn = (key: string, fraction: number, words?: number) => void;
const progressFns = new Set<ProgressFn>();
export function onProgress(fn: ProgressFn): () => void { progressFns.add(fn); return () => progressFns.delete(fn); }
function emitProgress(): void {
  if (!now || now.basmalah || !progressFns.size) return;
  const t = audio.currentTime;
  const end = segmentEnd !== null && Number.isFinite(segmentEnd) ? segmentEnd : audio.duration;
  const start = audio.dataset.file ? segmentStart : 0;
  if (!Number.isFinite(end) || end <= start) return;
  const fraction = Math.min(1, Math.max(0, (t - start) / (end - start)));
  const key = `${now.surah}:${now.ayah}`;
  let words: number | undefined;
  const r = reciterById(now.plan.reciter);
  if (audio.dataset.file && qdcFiles.has(r.id)) {
    const k = `${r.id}/${now.surah}`;
    const known = loadedWords.get(k);
    if (known) {
      // A word shows as it begins (a moment early, so it's there as it's heard).
      const ms = t * 1000 + 120;
      const segs = known[key];
      if (segs) words = segs.filter(([, from]) => from <= ms).reduce((n, [w]) => Math.max(n, w), 0);
    } else void wordTimes(r, now.surah)?.then((w) => loadedWords.set(k, w), () => undefined);
  }
  progressFns.forEach((fn) => fn(key, fraction, words));
}
// Several times a second while playing (timeupdate alone is too coarse to follow words).
window.setInterval(() => { if (now?.playing && !audio.paused) emitProgress(); }, 100);

const tell = (error?: string) => listeners.forEach((fn) => fn(now, error));
export const nowPlaying = () => now;

const order = (s: number, a: number) => s * 1000 + a;
/** Surahs other than Al-Fatihah and At-Tawbah open with the basmalah. */
const opensWithBasmalah = (s: number, a: number) => a === 1 && s !== 1 && s !== 9;
/** The ayah after [s, a], or null after the last ayah of the Quran. */
function nextAyah(s: number, a: number): [number, number] | null {
  if (a < (getChapter(s)?.verses_count ?? 0)) return [s, a + 1];
  return s < 114 ? [s + 1, 1] : null;
}
function prevAyah(s: number, a: number): [number, number] | null {
  if (a > 1) return [s, a - 1];
  return s > 1 ? [s - 1, getChapter(s - 1)?.verses_count ?? 1] : null;
}
const isLast = (n: NowPlaying) => order(n.surah, n.ayah) >= order(...n.plan.to);

export function play(plan: PlayPlan): void {
  stop();
  const [s, a] = plan.from;
  now = { plan, surah: s, ayah: a, ayahRound: 1, rangeRound: 1, basmalah: opensWithBasmalah(s, a), playing: true };
  start();
}

export function setSpeed(speed: number): void {
  if (!now) return;
  now.plan.speed = speed;
  audio.playbackRate = speed;
  tell();
}

export function toggle(): void {
  if (!now) return;
  if (now.playing) { audio.pause(); clearTimeout(pauseTimer); now.playing = false; tell(); }
  else { now.playing = true; if (between) advance(); else if (audio.src && !audio.ended) void audio.play(); else start(); tell(); }
}

export function stop(): void {
  token++;
  clearTimeout(pauseTimer);
  audio.pause();
  audio.removeAttribute('src');
  audio.dataset.file = '';
  segmentEnd = null;
  continuing = false;
  between = false;
  if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; }
  if (now) { now = null; tell(); }
}

/** Jump to the next (1) or previous (-1) ayah in the range. */
export function skip(direction: 1 | -1): void {
  if (!now) return;
  const next = direction === 1 ? nextAyah(now.surah, now.ayah) : prevAyah(now.surah, now.ayah);
  if (!next || order(...next) < order(...now.plan.from) || order(...next) > order(...now.plan.to)) return;
  [now.surah, now.ayah] = next;
  now.ayahRound = 1;
  now.basmalah = direction === 1 && opensWithBasmalah(...next);
  now.playing = true;
  start();
}

async function start(): Promise<void> {
  if (!now) return;
  const mine = ++token;
  clearTimeout(pauseTimer);
  const r = reciterById(now.plan.reciter);
  const [s, a] = now.basmalah ? [1, 1] : [now.surah, now.ayah];
  tell();
  mediaSession(r);
  await settled(r);
  if (mine !== token || !now) return;

  if (fileAyah(r, s, a) === null) {
    // No recording of this ayah by this reciter: say so, then carry on.
    const only = order(...now.plan.from) === order(...now.plan.to);
    tell(`${r.name}’s recording of ${s}:${a} is missing from the source${only ? '.' : ', so it’s skipped.'}`);
    if (only) { now.playing = false; return; }
    pauseTimer = window.setTimeout(() => {
      if (mine !== token || !now) return;
      advance(true);
    }, 2500);
    return;
  }

  between = false;
  if (wholeSurah(r)) { await startSegment(r, s, a, mine); return; }

  const blob = await savedBlob(r, s, a);
  if (mine !== token) return;
  if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; }
  segmentEnd = null;
  audio.dataset.file = '';
  const sources = blob ? [(blobUrl = URL.createObjectURL(blob))] : addresses(r, s, a);
  for (const src of sources) {
    audio.src = src;
    audio.playbackRate = now.plan.speed;
    try {
      await audio.play();
      if (!blob) rememberBase(r, src);
      return;
    } catch (e) {
      if (mine !== token) return;
      if ((e as DOMException).name === 'NotAllowedError') { now.playing = false; tell(); return; }
    }
  }
  if (mine !== token) return;
  cannotPlay();
}

function cannotPlay(): void {
  if (!now) return;
  now.playing = false;
  tell(navigator.onLine ? 'This recording couldn’t be played.' : 'You’re offline and this surah isn’t downloaded for this reciter.');
}

/** Play one ayah out of a whole-surah recording: seek to its start, stop at its end. */
async function startSegment(r: Reciter, surah: number, ayah: number, mine: number): Promise<void> {
  if (!now) return;
  const seg = await segment(r, now.surah, now.ayah, now.basmalah).catch(() => null);
  if (mine !== token || !now) return;
  if (!seg) { cannotPlay(); return; }
  void surah; void ayah;
  // Reuse the loaded file when the next ayah is in the same one.
  const key = `${r.id}/${seg.file}`;
  if (audio.dataset.file !== key) {
    const blob = await savedBlob(r, seg.file, 1);
    if (mine !== token) return;
    if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; }
    audio.src = blob ? (blobUrl = URL.createObjectURL(blob)) : addresses(r, seg.file, 1)[0];
    audio.dataset.file = key;
    await new Promise<void>((done) => {
      if (audio.readyState >= 1) { done(); return; }
      const ok = () => { audio.removeEventListener('loadedmetadata', ok); audio.removeEventListener('error', ok); done(); };
      audio.addEventListener('loadedmetadata', ok);
      audio.addEventListener('error', ok);
    });
    if (mine !== token || !now) return;
    if (audio.error) { audio.dataset.file = ''; cannotPlay(); return; }
  }
  // Continuing straight on (next ayah, no repeat or pause): don't seek, so there's no gap.
  const jump = !continuing || audio.paused;
  continuing = false;
  if (jump) {
    await metadata();
    audio.currentTime = seg.from;
  }
  segmentEnd = seg.to;
  segmentStart = seg.from;
  audio.playbackRate = now.plan.speed;
  try {
    await audio.play();
    watchSegment();
  } catch (e) {
    if (mine !== token || !now) return;
    if ((e as DOMException).name === 'NotAllowedError') { now.playing = false; tell(); return; }
    cannotPlay();
    return;
  }
  // iPhone Safari may only finish a jump once playback has started, so the
  // jump is checked while playing and made again if it didn't take.
  if (jump) void confirmJump(r, seg, mine);
}

/** Wait until the recording's length is known (needed before jumping into it). */
async function metadata(): Promise<void> {
  if (audio.readyState >= 1) return;
  await new Promise<void>((done) => {
    const ok = () => { audio.removeEventListener('loadedmetadata', ok); done(); };
    audio.addEventListener('loadedmetadata', ok);
    window.setTimeout(ok, 8000);
  });
}

const landed = (from: number, to: number) => audio.currentTime >= from - 0.5 && audio.currentTime < Math.max(from + 0.5, to);

async function confirmJump(r: Reciter, seg: { file: number; from: number; to: number }, mine: number): Promise<void> {
  for (let attempt = 0; attempt < 3; attempt++) {
    await new Promise((res) => window.setTimeout(res, 400));
    if (mine !== token || !now) return;
    if (landed(seg.from, seg.to)) return;
    audio.currentTime = seg.from;
  }
  await new Promise((res) => window.setTimeout(res, 400));
  if (mine !== token || !now || landed(seg.from, seg.to)) return;
  // The server won't let the player jump into the file: load the whole surah
  // into memory, where it always can, and jump there.
  if (blobUrl && audio.src === blobUrl) return;
  tell('Loading the whole surah recording…');
  try {
    const res = await fetch(addresses(r, seg.file, 1)[0]);
    if (!res.ok) throw new Error();
    const blob = await res.blob();
    if (mine !== token || !now) return;
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    audio.src = blobUrl = URL.createObjectURL(blob);
    await metadata();
    audio.currentTime = seg.from;
    await audio.play();
    watchSegment();
    tell();
  } catch { if (mine === token) cannotPlay(); }
}

/** Stop at the end of the current ayah (checked every frame, and on timeupdate as a backstop). */
function watchSegment(): void {
  const check = () => {
    if (segmentEnd === null || audio.paused) return;
    if (audio.currentTime >= segmentEnd - 0.02) { segmentEnd = null; finished(true); return; }
    requestAnimationFrame(check);
  };
  requestAnimationFrame(check);
}
audio.addEventListener('timeupdate', () => {
  emitProgress();
  if (segmentEnd !== null && audio.currentTime >= segmentEnd - 0.02) { segmentEnd = null; finished(true); }
});

audio.addEventListener('ended', () => { segmentEnd = null; finished(false); });

/**
 * One recitation is done. In a whole-surah file the audio keeps running into
 * the next ayah; it is left running only if that is exactly what comes next.
 */
function finished(inFile: boolean): void {
  if (!now) return;
  const mine = token;
  const p = now.plan;
  // (Only within a surah: the next surah is a different file.)
  const straightOn = inFile && !now.basmalah && p.pause === 0 && p.eachAyah === 1 && !isLast(now)
    && now.ayah < (getChapter(now.surah)?.verses_count ?? 0);
  // Pause only for the quiet gap (or the end); a repeat jumps back while playing.
  if (inFile && !straightOn && p.pause > 0) audio.pause();
  continuing = straightOn;
  between = true;
  const after = () => { if (mine === token && now) advance(); };
  const wait = now.basmalah ? 0 : now.plan.pause;
  if (wait > 0) pauseTimer = window.setTimeout(after, wait * 1000); else after();
}

/** Move on after a recitation; `skipRepeats` skips this ayah's remaining repeats. */
function advance(skipRepeats = false): void {
  if (!now) return;
  const p = now.plan;
  if (now.basmalah) { now.basmalah = false; start(); return; }
  if (!skipRepeats && (p.eachAyah === 0 || now.ayahRound < p.eachAyah)) { now.ayahRound++; start(); return; }
  now.ayahRound = 1;
  const next = nextAyah(now.surah, now.ayah);
  if (!isLast(now) && next) {
    [now.surah, now.ayah] = next;
    now.basmalah = opensWithBasmalah(...next);
    start();
    return;
  }
  if (p.wholeRange === 0 || now.rangeRound < p.wholeRange) {
    now.rangeRound++;
    [now.surah, now.ayah] = p.from;
    now.basmalah = opensWithBasmalah(...p.from);
    start();
    return;
  }
  now.playing = false;
  audio.pause();
  const done = now;
  now = null;
  listeners.forEach((fn) => fn(null));
  void done;
}

/** Lock-screen and headphone controls, where the device offers them. */
function mediaSession(r: Reciter): void {
  const ms = navigator.mediaSession;
  if (!ms || !now) return;
  try {
    ms.metadata = new MediaMetadata({ title: `${getChapter(now.surah)?.name_complex ?? ''} ${now.basmalah ? '' : now.ayah}`.trim(), artist: r.name, album: 'Hifz Mushaf' });
    ms.setActionHandler('play', () => { if (now && !now.playing) toggle(); });
    ms.setActionHandler('pause', () => { if (now?.playing) toggle(); });
    ms.setActionHandler('nexttrack', () => skip(1));
    ms.setActionHandler('previoustrack', () => skip(-1));
  } catch { /* not supported */ }
}
