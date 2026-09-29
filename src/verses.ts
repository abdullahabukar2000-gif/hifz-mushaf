// Verse by verse, like quran.com's: each ayah flows across the line, its
// words grouped by meaning, each group in a box. Below sits the translation,
// word for word as published; tap a box to reveal or hide the part of the
// sentence it means. Drag the edge between two boxes to regroup.

import { ayahGlyphs, getPage, glyphsVerified, loadPages, loadTranslations, meaningEnds, surahOfPage, TOTAL_PAGES, TRANSLATION_NAME, translationOf, translationPieces } from './data';
import { ensureFont, isConfirmed, pageFamily } from './fonts';
import { moveBreak, phrasesOf, resetToSuggested, toggleBreak, usesSuggestion, type Phrase } from './notes';
import { ayahLabel, h } from './dom';
import { iconButton } from './icons';

export interface VerseOptions {
  coverTranslations: boolean;
  /** Font for the Arabic: '' for the mushaf's own glyphs, else a CSS font family. */
  arabicFamily: string;
}

/** Which boxes show their English, per ayah, once the memoriser has tapped any. */
const revealed = new Map<string, Set<number>>();

/** The options verse by verse was last drawn with (for redrawing one ayah from outside). */
let shownWith: VerseOptions | null = null;

/** Recitation marks per ayah: word index -> 'ok' | 'err'. */
function redraw(key: string): void {
  const el = document.getElementById(`ayah-${key.replace(':', '-')}`);
  if (el && shownWith) el.replaceWith(renderAyah(key, shownWith));
}

/**
 * Reveal every box the recitation has reached (its first word is among the
 * first `wordsReached` words), just as if it had been tapped.
 */
export function revealWords(key: string, wordsReached: number): void {
  if (!shownWith) return;
  const phrases = phrasesOf(key);
  const set = revealSet(key, phrases, shownWith);
  let changed = false;
  for (const p of phrases) if (p.start < wordsReached && !set.has(p.start)) { set.add(p.start); changed = true; }
  if (changed) redraw(key);
}

/** Words heard so far per ayah (recited or played): they fill in when the Arabic is hidden. */
const heardUpTo = new Map<string, number>();
export function fillWords(key: string, words: number): void {
  if ((heardUpTo.get(key) ?? 0) >= words) return;
  heardUpTo.set(key, words);
  document.getElementById(`ayah-${key.replace(':', '-')}`)?.querySelectorAll<HTMLElement>('.vw[data-index]').forEach((span) => {
    if (Number(span.dataset.index) < words) span.classList.add('heard');
  });
}
export function clearHeard(): void {
  heardUpTo.clear();
  document.querySelectorAll('.vw.heard').forEach((el) => el.classList.remove('heard'));
}

/** Called when "hide translations" is switched: every ayah goes back to the new default. */
export function resetReveals(): void { revealed.clear(); }

const isRevealed = (key: string, start: number, options: VerseOptions) =>
  revealed.get(key)?.has(start) ?? !options.coverTranslations;

function revealSet(key: string, phrases: Phrase[], options: VerseOptions): Set<number> {
  let set = revealed.get(key);
  if (!set) {
    set = new Set(options.coverTranslations ? [] : phrases.map((p) => p.start));
    revealed.set(key, set);
  }
  return set;
}

function toggleReveal(key: string, start: number, phrases: Phrase[], options: VerseOptions): void {
  const set = revealSet(key, phrases, options);
  if (set.has(start)) set.delete(start); else set.add(start);
}

/** How many pages verse by verse adds at a time as you scroll. */
const BATCH = 3;

/**
 * Verse by verse from `startPage` on. More pages are added as you near the
 * bottom; a button at the top adds the pages before. `ready` resolves once the
 * first pages are on screen.
 */
export function renderVerses(startPage: number, options: VerseOptions): { root: HTMLElement; ready: Promise<void> } {
  shownWith = options;
  const root = h('div', { class: 'verses' });
  root.append(h('p', { class: 'verses-hint' },
    'Each box is one piece of meaning. Tap it to show or hide that part of the translation. Drag the edge between two boxes to move words across; double-tap a word to split its box there.'));
  const body = h('div', { class: 'verses-body' });
  const loading = h('p', { class: 'verses-loading', role: 'status' }, 'Loading…');
  const sentinel = h('div', { class: 'verses-sentinel' });
  const earlier = iconButton(h('button', { type: 'button', class: 'btn verses-earlier' }), 'chevronUp', 'Earlier pages');
  root.append(earlier, body, loading, sentinel,
    h('p', { class: 'verses-source' }, `Translation: ${TRANSLATION_NAME}, unchanged. Groups follow its meaning.`));

  const seen = new Set<string>();
  let first = startPage;
  let last = startPage - 1;
  let busy: Promise<void> | null = null;

  /** Render pages `from`..`to`, each ayah once, with the pages each ayah touches loaded first. */
  async function build(from: number, to: number): Promise<DocumentFragment> {
    const nums = Array.from({ length: to - from + 1 }, (_, i) => from + i);
    await Promise.all([loadTranslations(), loadPages([from - 1, ...nums, to + 1])]);
    const frag = document.createDocumentFragment();
    for (const n of nums) {
      const data = getPage(n);
      if (!data) continue;
      const chapter = surahOfPage(data);
      const heading = h('p', { class: 'verses-page' }, `${chapter?.name_complex ?? ''} · page ${n}`);
      heading.dataset.page = String(n);
      frag.append(heading);
      for (const key of data.verses) {
        if (seen.has(key)) continue;
        seen.add(key);
        frag.append(renderAyah(key, options));
      }
    }
    return frag;
  }

  const more = () => {
    if (busy || last >= TOTAL_PAGES) return busy;
    const from = last + 1;
    const to = Math.min(TOTAL_PAGES, last + BATCH);
    busy = build(from, to).then((frag) => {
      body.append(frag);
      last = to;
      if (last >= TOTAL_PAGES) loading.remove();
    }).catch(() => { loading.textContent = 'Couldn’t load more pages. Scroll again to retry.'; })
      .finally(() => { busy = null; });
    return busy;
  };

  const updateEarlier = () => { earlier.hidden = first <= 1; };
  earlier.addEventListener('click', async () => {
    if (first <= 1) return;
    const from = Math.max(1, first - BATCH);
    const frag = await build(from, first - 1);
    // Keep what you were reading where it was while the earlier pages go in above.
    const scroller = root.parentElement;
    const before = body.scrollHeight;
    body.prepend(frag);
    if (scroller) scroller.scrollTop += body.scrollHeight - before;
    first = from;
    updateEarlier();
  });
  updateEarlier();

  new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) more();
  }, { rootMargin: '1200px 0px' }).observe(sentinel);

  const ready = more() ?? Promise.resolve();
  return { root, ready: ready.then(() => undefined) };
}

export function renderAyah(key: string, options: VerseOptions): HTMLElement {
  const article = h('article', { class: 'ayah', id: `ayah-${key.replace(':', '-')}` });
  article.dataset.key = key;
  let current = article;
  const rerender = () => {
    const next = renderAyah(key, options);
    current.replaceWith(next);
    current = next;
    return next;
  };

  // --- heading: where, and whether the grouping is the suggestion or yours
  const suggestedNow = usesSuggestion(key);
  const head = h('header', { class: 'ayah-head' },
    h('span', { class: 'ayah-num' }, key),
    h('span', { class: 'ayah-name' }, ayahLabel(key).replace(/ \d+$/, '')),
    h('span', { class: 'ayah-status' }, suggestedNow ? 'grouped by meaning' : 'your groups'));
  const listen = iconButton(h('button', { type: 'button', class: 'btn small icon-only ayah-play' }), 'play', `Play from ${key}`);
  listen.addEventListener('click', () => document.dispatchEvent(new CustomEvent('play-ayah', { detail: key })));
  head.append(listen);
  if (!suggestedNow) {
    const reset = iconButton(h('button', { type: 'button', class: 'btn small' }), 'undo', 'use suggestion');
    reset.addEventListener('click', () => { resetToSuggested(key); rerender(); });
    head.append(reset);
  }

  // --- the ayah, flowing across the line, one box per phrase
  const phrases = phrasesOf(key);
  const glyphs = ayahGlyphs(key);
  const text = h('div', { class: 'ayah-text', dir: 'rtl', lang: 'ar' });
  phrases.forEach((p, i) => {
    const last = i === phrases.length - 1;
    const open = isRevealed(key, p.start, options);
    const box = h('button', { type: 'button', class: `box${open ? ' open' : ''}`, 'aria-pressed': String(open) });
    box.dataset.start = String(p.start);
    for (const { page, word } of glyphs) {
      const w = word.pos - 1;
      if (word.type !== 'word' || w < p.start || w > p.end) continue;
      const span = h('span', { class: 'vw' }, word.uthmani);
      span.dataset.page = String(page);
      span.dataset.code = word.code;
      span.dataset.index = String(w);
      if (w < (heardUpTo.get(key) ?? 0)) span.classList.add('heard');
      box.append(span);
    }
    box.addEventListener('click', () => { toggleReveal(key, p.start, phrases, options); rerender(); });
    box.addEventListener('dblclick', (e) => {
      const index = Number((e.target as HTMLElement).closest<HTMLElement>('.vw')?.dataset.index);
      if (Number.isInteger(index) && index < p.end) { toggleBreak(key, index); rerender(); }
    });

    const unit = h('span', { class: 'box-unit' }, box);
    if (!last) unit.append(edge(key, p, rerender));
    else {
      const marker = glyphs.find((g) => g.word.type === 'end');
      if (marker) {
        const span = h('span', { class: 'vw end' }, marker.word.uthmani);
        span.dataset.page = String(marker.page);
        span.dataset.code = marker.word.code;
        unit.append(span);
      }
    }
    text.append(unit);
  });
  if (options.arabicFamily) text.style.fontFamily = options.arabicFamily;
  else upgradeGlyphs(text);

  article.append(head, text, english(key, phrases, options, rerender));
  return article;
}

/**
 * The translation under the ayah, exactly as published. Each piece of it
 * belongs to a meaning group; it shows when any box holding that group's
 * words is revealed. Tapping a piece reveals (or hides) those boxes.
 */
function english(key: string, phrases: Phrase[], options: VerseOptions, rerender: () => void): HTMLElement {
  const line = h('p', { class: 'english-line' });
  const pieces = translationPieces(key);
  const ends = meaningEnds(key);
  const set = () => revealSet(key, phrases, options);
  const isOpen = (p: Phrase) => revealed.get(key)?.has(p.start) ?? !options.coverTranslations;

  if (!pieces || !ends) {
    // Not matched to the translation yet: the sentence shows once any box is revealed.
    const text = translationOf(key) ?? 'No translation saved for this ayah yet.';
    const open = phrases.some(isOpen);
    line.append(h('span', { class: `english-part${open ? ' open' : ''}` }, text));
    return h('div', { class: 'ayah-english' }, line);
  }

  const boxesFor = (group: number) => {
    const lo = group ? ends[group - 1] + 1 : 0;
    const hi = ends[group];
    return phrases.filter((p) => p.start <= hi && p.end >= lo);
  };
  for (const piece of pieces) {
    const boxes = boxesFor(piece.group);
    const open = boxes.some(isOpen);
    // A span, not a button, so a long piece wraps with the sentence like ordinary text.
    const part = h('span', { class: `english-part${open ? ' open' : ''}`, role: 'button', tabindex: '0' }, piece.text);
    part.setAttribute('aria-label', open ? piece.text : 'Hidden. Tap to reveal.');
    const flip = () => {
      const s = set();
      if (open) boxes.forEach((b) => s.delete(b.start)); else boxes.forEach((b) => s.add(b.start));
      rerender();
    };
    part.addEventListener('click', flip);
    part.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flip(); } });
    line.append(piece.before, part);
  }
  return h('div', { class: 'ayah-english' }, line);
}

/**
 * The edge after phrase `p`. Drag it over a word and the boundary moves there:
 * the box before ends at that word. Drag it past a whole box and the two join.
 * Arrow keys move it a word at a time.
 */
function edge(key: string, p: Phrase, rerender: () => HTMLElement): HTMLElement {
  const grip = h('span', {
    class: 'edge',
    role: 'slider',
    tabindex: '0',
    'aria-label': 'Boundary between two groups: drag left or right, or use the arrow keys',
    'aria-valuenow': String(p.end + 1),
  });
  grip.dataset.end = String(p.end);

  grip.addEventListener('keydown', (e) => {
    // Right to left: the left arrow moves the edge on through the ayah.
    const step = e.key === 'ArrowLeft' ? 1 : e.key === 'ArrowRight' ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    e.stopPropagation();
    moveBreak(key, p.end, p.end + step);
    rerender().querySelector<HTMLElement>(`.edge[data-end="${p.end + step}"]`)?.focus();
  });

  grip.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    let end = p.end;
    document.body.classList.add('dragging');
    let live = grip;
    live.classList.add('active');
    const move = (ev: PointerEvent) => {
      const under = document.elementFromPoint(ev.clientX, ev.clientY)?.closest<HTMLElement>('.vw:not(.end)');
      const article = under?.closest<HTMLElement>('.ayah');
      if (!under || article?.dataset.key !== key) return;
      const target = Number(under.dataset.index);
      if (!Number.isInteger(target) || target === end) return;
      moveBreak(key, end, target);
      const next = rerender();
      const still = phrasesOf(key).some((q) => q.end === target);
      if (!still) { stop(); return; }
      end = target;
      live = next.querySelector<HTMLElement>(`.edge[data-end="${target}"]`) ?? live;
      live.classList.add('active');
    };
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
      window.removeEventListener('pointercancel', stop);
      document.body.classList.remove('dragging');
      document.querySelectorAll('.edge.active').forEach((n) => n.classList.remove('active'));
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop);
    window.addEventListener('pointercancel', stop);
  });
  return grip;
}

/** Glyph codes only once each word's own page font is confirmed; Unicode until then. */
function upgradeGlyphs(container: HTMLElement): void {
  const byPage = new Map<number, HTMLElement[]>();
  for (const span of container.querySelectorAll<HTMLElement>('.vw')) {
    const page = Number(span.dataset.page);
    if (!byPage.has(page)) byPage.set(page, []);
    byPage.get(page)!.push(span);
  }
  for (const [page, spans] of byPage) {
    // Typed-text pages keep their Unicode words here too.
    if (!glyphsVerified(page)) continue;
    const family = pageFamily(page);
    const apply = () => spans.forEach((s) => { s.textContent = s.dataset.code!; s.style.fontFamily = `"${family}"`; s.classList.add('glyph'); });
    if (isConfirmed(family)) { apply(); continue; }
    const sample = getPage(page)!.lines.flatMap((l) => l.words.map((w) => w.code)).join('');
    ensureFont(family, sample).then((ok) => { if (ok) apply(); });
  }
}
