// Bundled, not fetched from Google, so the app works with the wifi off.
import '@fontsource-variable/newsreader/opsz.css';
import '@fontsource/amiri-quran/arabic-400.css';
import '@fontsource/scheherazade-new/arabic-400.css';
import '@fontsource/noto-naskh-arabic/arabic-400.css';
import './styles/tokens.css';
import './styles/app.css';
import { ayahRange, availablePages, getChapter, getPage, loadIndex, loadPages, pagesOfAyah, surahsOnPage, TOTAL_PAGES } from './data';
import { loadFontUrls } from './fonts';
import { iconButton, type IconName } from './icons';
import { renderPage, upgradeToGlyphs } from './render';
import { renderVerses, resetReveals } from './verses';
import { renderHome } from './home';
import { countText, renderSettings, scriptFamily, syncLine, type Mood, type Prefs, type Script } from './settings';
import { onChange } from './notes';
import { claudeHost, onSyncState, startSync } from './sync';
import { mountPlayerBar, openPlayerSheet, playFrom } from './player';
import { onPlayer, onProgress, stop } from './recite';
import { clearHeard, fillWords, revealWords } from './verses';
import { h } from './dom';
import { ayahWords } from './data';
import { registerOffline } from './offline';

type View = 'home' | 'mushaf' | 'verses' | 'settings';
type Layout = 'single' | 'spread';

const stage = document.querySelector<HTMLElement>('#stage')!;
const title = document.querySelector<HTMLElement>('#title')!;
const subtitle = document.querySelector<HTMLElement>('#subtitle')!;
const layoutButton = document.querySelector<HTMLButtonElement>('#layout')!;
const hideButton = document.querySelector<HTMLButtonElement>('#hide')!;
const nextButton = document.querySelector<HTMLButtonElement>('#next')!;
const prevButton = document.querySelector<HTMLButtonElement>('#prev')!;
const listenButton = document.querySelector<HTMLButtonElement>('#listen')!;
const tabs = document.querySelectorAll<HTMLButtonElement>('#tabs [data-view]');

const store = {
  get(key: string) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* private mode */ } },
};

const VIEWS: View[] = ['home', 'mushaf', 'verses', 'settings'];
let view: View = VIEWS.includes(store.get('view') as View) ? store.get('view') as View : 'home';
let layout: Layout = store.get('layout') === 'spread' ? 'spread' : 'single';
/**
 * What's hidden and revealed as a reciter plays: nothing ('off'), only the
 * translation ('english', the Arabic stays), or both ('both').
 */
type RevealMode = 'off' | 'english' | 'both';
let revealMode: RevealMode = (['off', 'english', 'both'] as RevealMode[]).find((m) => m === store.get('reveal-mode'))
  ?? (store.get('hide-arabic') === 'yes' ? 'both' : store.get('cover') === 'yes' ? 'english' : 'off');
let coverTranslations = revealMode !== 'off';
let hideArabic = revealMode === 'both';
const savedPage = Number(store.get('page'));
let lastPage: number | null = savedPage >= 1 && savedPage <= TOTAL_PAGES ? savedPage : null;
const prefs: Prefs = {
  mood: (['auto', 'chalk', 'sepia', 'night'] as Mood[]).find((m) => m === store.get('mood')) ?? 'auto',
  script: (['mushaf', 'amiri', 'scheherazade', 'naskh'] as Script[]).find((s) => s === store.get('script')) ?? 'mushaf',
};

// ------------------------------------------------------------------ chrome

const TAB_ICONS: Record<View, [IconName, string]> = {
  home: ['home', 'Home'], mushaf: ['book', 'Mushaf'], verses: ['rows', 'Verse by verse'], settings: ['gear', 'Settings'],
};
tabs.forEach((t) => { const [i, l] = TAB_ICONS[t.dataset.view as View]; iconButton(t, i, l); });
iconButton(nextButton, 'chevronLeft', 'Next page');
iconButton(prevButton, 'chevronRight', 'Previous page');
iconButton(listenButton, 'headphones', 'Listen');
mountPlayerBar(document.querySelector<HTMLElement>('#player')!, () => pageInView());

function applyMood(): void {
  if (prefs.mood === 'auto') delete document.documentElement.dataset.mood;
  else document.documentElement.dataset.mood = prefs.mood;
}

// Wide screens: the top bar and the tabs line up with what's on the page (the
// mushaf page, the verse column, the surah list), whatever its width.
const topbar = document.querySelector<HTMLElement>('#topbar')!;
const tabBar = document.querySelector<HTMLElement>('#tabs')!;
function alignBars(): void {
  if (innerWidth < 900) { topbar.style.paddingInline = ''; tabBar.style.paddingInline = ''; return; }
  const boxes = [...stage.querySelectorAll<HTMLElement>('.page, .verses, #stage > :not(.strip)')]
    .map((e) => e.getBoundingClientRect())
    .filter((b) => b.width > 0 && b.right > 0 && b.left < innerWidth && b.width < innerWidth - 40);
  if (!boxes.length) { topbar.style.paddingInline = ''; tabBar.style.paddingInline = ''; return; }
  const left = Math.min(...boxes.map((b) => b.left));
  const right = innerWidth - Math.max(...boxes.map((b) => b.right));
  const side = Math.max(16, Math.min(left, right));
  topbar.style.paddingInline = `${side}px`;
  tabBar.style.paddingInline = `${side}px`;
}
addEventListener('resize', () => requestAnimationFrame(alignBars));
void document.fonts?.ready.then(() => alignBars());
window.setTimeout(alignBars, 1500);
new ResizeObserver(() => requestAnimationFrame(alignBars)).observe(stage);
new MutationObserver(() => requestAnimationFrame(alignBars)).observe(stage, { childList: true });
stage.addEventListener('scroll', () => requestAnimationFrame(alignBars), { passive: true });

function updateChrome(): void {
  document.body.dataset.view = view;
  requestAnimationFrame(() => requestAnimationFrame(alignBars));
  stage.dataset.view = view;
  stage.dataset.layout = layout;
  tabs.forEach((t) => {
    if (t.dataset.view === view) t.setAttribute('aria-current', 'page'); else t.removeAttribute('aria-current');
  });
  iconButton(layoutButton, layout === 'single' ? 'twoPages' : 'onePage', layout === 'single' ? 'Two pages' : 'One page');
  iconButton(hideButton, revealMode === 'off' ? 'eye' : 'eyeOff', 'Reveal as recited');
  hideButton.setAttribute('aria-pressed', String(revealMode !== 'off'));
  hideButton.setAttribute('aria-haspopup', 'menu');
  document.body.classList.toggle('hide-arabic', hideArabic);
  updateTitle();
}

function updateTitle(): void {
  if (view === 'home') { title.textContent = 'Hifz Mushaf'; subtitle.textContent = 'حفظ'; subtitle.lang = 'ar'; return; }
  if (view === 'settings') { title.textContent = 'Settings'; subtitle.textContent = ''; return; }
  subtitle.lang = 'en';
  const page = pageInView();
  const shown = view === 'mushaf' && layout === 'spread' ? currentSlot() ?? [page] : [page];
  // Every surah on screen, as a page where one surah ends and the next begins holds both.
  const surahs = [...new Set(shown.flatMap(surahsOnPage))];
  title.textContent = surahs.map((id) => getChapter(id)?.name_complex ?? '').join(' · ');
  const pages = view === 'mushaf' && layout === 'spread' ? currentSlot()?.join('–') : String(page);
  subtitle.textContent = view === 'verses' ? `Verse by verse · page ${page}` : `Page ${pages}`;
}

// ------------------------------------------------------------------ views

/** Pages grouped as they sit on screen: one per slot, or an odd (right) and even (left) pair. */
function slotsOf(): number[][] {
  if (layout === 'single') return availablePages.map((n) => [n]);
  const slots: number[][] = [];
  for (const n of availablePages) {
    const right = n % 2 ? n : n - 1;
    const last = slots[slots.length - 1];
    if (last && last[0] === right) last.push(n);
    else slots.push([n]);
  }
  return slots;
}

/** Redraw the current view; mushaf and verse by verse open at `page`. */
function show(page = lastPage ?? 1): void {
  updateChrome();
  stage.scrollTop = 0;
  verseJob = null;
  if (view === 'home') {
    stage.replaceChildren(renderHome(lastPage, { openPage }));
    return;
  }
  if (view === 'settings') {
    // The script samples are real words from page 255, so it loads first.
    stage.replaceChildren();
    loadPages([255]).catch(() => undefined).then(() => {
      if (view === 'settings') stage.replaceChildren(renderSettings(prefs, changePrefs));
    });
    return;
  }
  if (view === 'verses') {
    const { root, ready } = renderVerses(page, { coverTranslations, arabicFamily: scriptFamily(prefs.script) });
    stage.replaceChildren(root);
    verseJob = ready;
    return;
  }
  // The mushaf, swiped sideways: laid out right to left, so the first page
  // sits at the right and the next one comes in from the left, as in print.
  // Only the page you're on and two either side are in the strip; it moves
  // along as you swipe. (A strip of all 604 pages meant jumps of up to
  // 200,000 pixels, which iPhone Safari doesn't always land correctly.)
  stage.replaceChildren();
  showSlot(slotIndexOf(page));
}

let verseJob: Promise<void> | null = null;

function fillSlot(slot: HTMLElement): void {
  if (slot.dataset.filled) return;
  slot.dataset.filled = 'yes';
  const pages = slot.dataset.pages!.split(',').map(Number);
  loadPages(pages).then(() => {
    if (!slot.dataset.filled || slot.childElementCount) return;
    const spread = document.createElement('div');
    spread.className = 'spread';
    spread.dir = 'rtl';
    for (const n of pages) {
      const data = getPage(n)!;
      const pageEl = renderPage(data);
      spread.append(pageEl);
      queueMicrotask(() => upgradeToGlyphs(pageEl, data));
    }
    slot.append(spread);
  }).catch(() => {
    delete slot.dataset.filled;
    slot.replaceChildren(Object.assign(document.createElement('p'), { className: 'slot-error', textContent: 'This page couldn’t load. Swipe away and back to try again.' }));
  });
}

function currentSlot(): number[] | undefined {
  return slotsOf().find((s) => s.includes(pageInView()));
}

/** The page you're looking at: the slot filling the screen, or the page heading nearest the top. */
function pageInView(): number {
  const box = stage.getBoundingClientRect();
  if (view === 'mushaf') {
    const slot = visibleSlot();
    return slot ? Number(slot.dataset.page) : lastPage ?? 1;
  }
  if (view === 'verses') {
    let current = lastPage ?? 1;
    for (const el of stage.querySelectorAll<HTMLElement>('.verses-page')) {
      if (el.getBoundingClientRect().top <= box.top + stage.clientHeight / 3) current = Number(el.dataset.page);
    }
    return current;
  }
  return lastPage ?? availablePages[0];
}

function scrollToPage(page: number, smooth = false): void {
  if (view === 'mushaf') {
    const index = slotIndexOf(page);
    const el = stage.querySelector<HTMLElement>(`.slot[data-index="${index}"]`);
    // A neighbouring page already in the strip slides in; anything else is placed directly.
    if (smooth && el) stage.scrollTo({ left: offsetOf(Number(el.dataset.local)), behavior: 'smooth' });
    else showSlot(index);
  } else if (view === 'verses') {
    const heading = stage.querySelector<HTMLElement>(`.verses-page[data-page="${page}"]`);
    if (heading) stage.scrollTop += heading.getBoundingClientRect().top - stage.getBoundingClientRect().top;
  }
  remember();
}

// ------------------------------------------------------------------ the mushaf strip

const AROUND = 2;
const slotIndexOf = (page: number) => Math.max(0, slotsOf().findIndex((s) => s.includes(page)));

/** The slot filling the screen. */
function visibleSlot(): HTMLElement | undefined {
  const left = stage.getBoundingClientRect().left;
  let best: HTMLElement | undefined;
  let bestDistance = Infinity;
  for (const slot of stage.querySelectorAll<HTMLElement>('.slot')) {
    const d = Math.abs(slot.getBoundingClientRect().left - left);
    if (d < bestDistance) { bestDistance = d; best = slot; }
  }
  return best;
}

/**
 * Scroll position of the strip's `local`-th slot. Right to left, browsers
 * count from 0 downwards (older ones upwards from the far end).
 */
function offsetOf(local: number): number {
  const x = local * stage.clientWidth;
  const probe = stage.scrollLeft;
  if (probe < 0) return -x;
  if (probe > 0) return stage.scrollWidth - stage.clientWidth - x;
  stage.scrollLeft = -1;
  const negative = stage.scrollLeft < 0;
  stage.scrollLeft = probe;
  return negative ? -x : x;
}

/** Put slot `index` (of all slots) on screen, with its neighbours either side. */
let placing = 0;
function showSlot(index: number): void {
  requestAnimationFrame(() => requestAnimationFrame(alignBars));
  const all = slotsOf();
  index = Math.min(Math.max(index, 0), all.length - 1);
  const from = Math.max(0, index - AROUND);
  const to = Math.min(all.length - 1, index + AROUND);
  const existing = new Map([...stage.querySelectorAll<HTMLElement>('.slot')].map((el) => [Number(el.dataset.index), el]));
  const strip: HTMLElement[] = [];
  for (let i = from; i <= to; i++) {
    let el = existing.get(i);
    if (!el || el.dataset.pages !== all[i].join(',')) {
      el = document.createElement('section');
      el.className = 'slot';
      el.dataset.index = String(i);
      el.dataset.page = String(all[i][0]);
      el.dataset.pages = all[i].join(',');
    }
    el.dataset.local = String(i - from);
    strip.push(el);
  }
  const run = ++placing;
  stage.style.scrollSnapType = 'none';
  stage.replaceChildren(...strip);
  strip.forEach(fillSlot);
  const target = offsetOf(index - from);
  stage.scrollLeft = target;
  // Check it landed (and put it right) for a few frames before snapping returns.
  let frames = 0;
  const check = () => {
    if (run !== placing) return;
    if (Math.abs(stage.scrollLeft - target) > 1) stage.scrollLeft = target;
    if (++frames < 6) { requestAnimationFrame(check); return; }
    stage.style.scrollSnapType = '';
    remember();
  };
  requestAnimationFrame(check);
}

/** After a swipe settles: if you've reached the end of the strip, move the strip along. */
function recentre(): void {
  if (view !== 'mushaf') return;
  const el = visibleSlot();
  if (!el) return;
  const local = Number(el.dataset.local);
  const count = stage.querySelectorAll('.slot').length;
  if (local === 0 || local === count - 1) {
    const index = Number(el.dataset.index);
    const last = slotsOf().length - 1;
    if ((local === 0 && index > 0) || (local === count - 1 && index < last)) showSlot(index);
  }
}

/** Keep the page in view for "Continue reading", and the title in step with it. */
function remember(): void {
  if (view !== 'mushaf' && view !== 'verses') return;
  lastPage = pageInView();
  store.set('page', String(lastPage));
  updateTitle();
}
let scrollTimer: number | undefined;
stage.addEventListener('scroll', () => {
  clearTimeout(scrollTimer);
  scrollTimer = window.setTimeout(() => { remember(); recentre(); }, 150);
}, { passive: true });

/** The ayah you chose to open (a surah's first ayah), kept while its page is in view. */
let focusKey: string | null = null;

function go(next: View, page?: number): void {
  const keep = page ?? (view === 'mushaf' || view === 'verses' ? pageInView() : lastPage ?? 1);
  if (focusKey && !pagesOfAyah(focusKey).includes(keep)) focusKey = null;
  view = next;
  store.set('view', view);
  show(keep);
  if (next === 'mushaf') scrollToPage(keep);
  if (next === 'verses') verseJob?.then(() => {
    if (view !== 'verses') return;
    // Straight to the chosen ayah when it's on this page (a surah that starts mid-page).
    const ayah = focusKey ? document.getElementById(`ayah-${focusKey.replace(':', '-')}`) : null;
    if (ayah) { stage.scrollTop += ayah.getBoundingClientRect().top - stage.getBoundingClientRect().top - 8; remember(); }
    else scrollToPage(keep);
  });
}

/** Redraw in place: the same page stays in view. */
function refresh(): void {
  if (view === 'mushaf' || view === 'verses') { go(view, pageInView()); return; }
  const scroll = stage.scrollTop;
  show();
  stage.scrollTop = scroll;
}

function openPage(page: number, target: 'mushaf' | 'verses', ayah?: string): void {
  focusKey = ayah ?? null;
  go(target, page);
}

function changePrefs(p: Partial<Prefs>): void {
  Object.assign(prefs, p);
  store.set('mood', prefs.mood);
  store.set('script', prefs.script);
  applyMood();
  refresh();
}

/** Move one slot on (1) or back (-1). */
function turn(direction: 1 | -1): void {
  const slots = slotsOf();
  const at = slots.findIndex((s) => s.includes(pageInView()));
  const next = slots[at + direction];
  if (next) scrollToPage(next[0], true);
}

// ------------------------------------------------------------------ wiring

tabs.forEach((t) => t.addEventListener('click', () => { if (t.dataset.view !== view) go(t.dataset.view as View); }));
layoutButton.addEventListener('click', () => {
  const page = pageInView();
  layout = layout === 'single' ? 'spread' : 'single';
  store.set('layout', layout);
  go('mushaf', page);
});
// Reveal as recited: a small menu of what to hide, which then fills in as the
// reciter you're listening to reaches each word (Arabic) and each meaning
// group (translation).
const REVEAL_CHOICES: [RevealMode, string, string][] = [
  ['off', 'Show everything', 'Arabic and translation always showing'],
  ['english', 'Reveal the translation', 'The Arabic stays; each meaning appears as it’s recited'],
  ['both', 'Reveal Arabic and translation', 'Each word and its meaning appear as they’re recited'],
];
function setReveal(mode: RevealMode): void {
  revealMode = mode;
  store.set('reveal-mode', mode);
  coverTranslations = mode !== 'off';
  hideArabic = mode === 'both';
  resetReveals();
  clearHeard();
  stage.querySelectorAll('.w.heard, .w.peek').forEach((el) => el.classList.remove('heard', 'peek'));
  updateChrome();
  refresh();
}
let revealMenu: HTMLElement | null = null;
function closeRevealMenu(): void { revealMenu?.remove(); revealMenu = null; hideButton.setAttribute('aria-expanded', 'false'); }
hideButton.addEventListener('click', (e) => {
  e.stopPropagation();
  if (revealMenu) { closeRevealMenu(); return; }
  const menu = h('div', { class: 'reveal-menu', role: 'menu' });
  for (const [mode, label, note] of REVEAL_CHOICES) {
    const item = h('button', { type: 'button', role: 'menuitemradio', class: 'reveal-item', 'aria-checked': String(mode === revealMode) },
      h('span', { class: 'reveal-label' }, label), h('span', { class: 'reveal-note' }, note));
    item.addEventListener('click', () => { closeRevealMenu(); setReveal(mode); });
    menu.append(item);
  }
  const b = hideButton.getBoundingClientRect();
  menu.style.top = `${b.bottom + 6}px`;
  menu.style.right = `${Math.max(8, innerWidth - b.right)}px`;
  document.body.append(menu);
  revealMenu = menu;
  hideButton.setAttribute('aria-expanded', 'true');
});
document.addEventListener('click', (e) => { if (revealMenu && !revealMenu.contains(e.target as Node)) closeRevealMenu(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeRevealMenu(); });
/** Fill in the first `words` words of an ayah (hidden Arabic). */
function fillIn(key: string, words: number): void {
  fillWords(key, words);
  stage.querySelectorAll<HTMLElement>(`.w[data-key="${key}"]:not(.end)`).forEach((span) => {
    if (Number(span.dataset.pos) <= words) span.classList.add('heard');
  });
}
// On the mushaf page, tap a hidden word to peek at it.
stage.addEventListener('click', (e) => {
  if (!hideArabic) return;
  (e.target as HTMLElement).closest<HTMLElement>('.w:not(.end)')?.classList.toggle('peek');
});
nextButton.addEventListener('click', () => turn(1));
// Listen: opens at the surah and first ayah of the page in view.
listenButton.addEventListener('click', () => {
  const first = ayahRange(pageInView())?.[0] ?? '1:1';
  const [surah, ayah] = first.split(':').map(Number);
  openPlayerSheet(pageInView(), surah, ayah);
});

// The ayah being recited is marked, in the mushaf and in verse by verse, and kept in view.
let marked = '';
onPlayer((n) => {
  const key = n && !n.basmalah ? `${n.surah}:${n.ayah}` : '';
  // An ayah the reciter has finished is shown in full.
  if (marked && key !== marked && hideArabic) { fillIn(marked, Infinity); if (view === 'verses') revealWords(marked, Infinity); }
  highlight(key);
});
function highlight(key: string): void {
  if (key === marked) return;
  stage.querySelectorAll('.reciting').forEach((el) => el.classList.remove('reciting'));
  marked = key;
  if (!key) return;
  const els = stage.querySelectorAll<HTMLElement>(`.ayah[data-key="${key}"], .w[data-key="${key}"]`);
  els.forEach((el) => el.classList.add('reciting'));
  follow(true);
}
/** Keeps the playing ayah centred in the verses view (scrolling only the verses
 * area: scrollIntoView could move the whole page, and the bars with it). An ayah
 * taller than the screen follows its words as they're recited instead. */
function follow(changed = false): void {
  if (view !== 'verses' || !marked) return;
  const el = stage.querySelector<HTMLElement>(`.ayah[data-key="${marked}"]`);
  if (!el) return;
  const box = el.getBoundingClientRect();
  const area = stage.getBoundingClientRect();
  let target: number;
  if (box.height < area.height * 0.8) {
    target = box.top + box.height / 2 - (area.top + area.height / 2);
    if (!changed && Math.abs(target) < area.height * 0.2) return;
  } else {
    const words = el.querySelectorAll<HTMLElement>('.heard');
    const last = words[words.length - 1];
    const y = last ? last.getBoundingClientRect().bottom : box.top;
    if (changed) target = box.top - area.top - 12;
    else if (y > area.bottom - area.height * 0.3) target = y - (area.top + area.height / 2);
    else return;
  }
  if (Math.abs(target) > 4) stage.scrollTo({ top: stage.scrollTop + target, behavior: 'smooth' });
}
let lastFollow = 0;
new MutationObserver(() => {
  if (!marked) return;
  stage.querySelectorAll<HTMLElement>(`.ayah[data-key="${marked}"]:not(.reciting), .w[data-key="${marked}"]:not(.reciting)`).forEach((el) => el.classList.add('reciting'));
}).observe(stage, { childList: true, subtree: true });
// Reveal as recited: as the reciter reaches each word, it shows (Arabic), and
// each meaning group opens as its first word is reached (translation). With
// quran.com's timings the words follow the recording exactly; otherwise where
// each word falls is estimated from the words' lengths.
onProgress((key, fraction, known) => {
  if (!hideArabic && view !== 'verses') return;
  let reached = known;
  if (reached === undefined) {
    const words = ayahWords(key);
    if (!words.length) return;
    const lengths = words.map((w) => w.length);
    const total = lengths.reduce((a, b) => a + b, 0);
    reached = 0;
    let before = 0;
    for (const len of lengths) {
      if (before / total > fraction + 0.02) break;
      reached++;
      before += len;
    }
  }
  if (hideArabic) fillIn(key, reached);
  if (view === 'verses') revealWords(key, reached);
  if (Date.now() - lastFollow > 700) { lastFollow = Date.now(); follow(); }
});

document.addEventListener('play-ayah', (e) => {
  const [surah, ayah] = (e as CustomEvent<string>).detail.split(':').map(Number);
  playFrom(surah, ayah);
});
prevButton.addEventListener('click', () => turn(-1));

// Arrow keys turn pages in the mushaf; left is forward, as the mushaf reads right to left.
document.addEventListener('keydown', (e) => {
  if (view !== 'mushaf' || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === 'ArrowLeft') { e.preventDefault(); turn(1); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); turn(-1); }
});

// Groups changed on another device arrive here; redraw what shows them.
onChange((key) => {
  if (key !== '*') return;
  if (view === 'settings') {
    const line = stage.querySelector('.work-count');
    if (line) line.textContent = countText();
    return;
  }
  if (view === 'verses') refresh();
});
onSyncState(() => {
  if (view !== 'settings') return;
  const line = stage.querySelector('.sync-line');
  if (line) line.replaceWith(syncLine());
});

applyMood();
updateChrome();
if (!claudeHost()) registerOffline();
// The small page index and the font list come first; pages load as they're reached.
Promise.all([loadIndex(), loadFontUrls()]).then(() => {
  go(view);
  startSync();
}).catch(() => {
  stage.textContent = 'The Quran pages couldn’t load. Check your connection and reload.';
});
