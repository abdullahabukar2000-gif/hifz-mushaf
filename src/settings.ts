// Settings: how it looks (theme, verse-by-verse script), where your work is
// kept (account sync, backup and restore), and where the text comes from.

import { ayahWords } from './data';
import { h } from './dom';
import { icon } from './icons';
import { editedCount } from './notes';
import { downloadBackup, readBackup, restoreBackup } from './backup';
import { claudeHost, syncState, type SyncState } from './sync';
import { deleteDownload, listDownloads, reciterById } from './recite';
import { megabytes } from './player';
import { canWorkOffline, mushafSaved, saveMushaf } from './offline';
import { getChapter } from './data';

declare const __BUILT__: string;

export type Mood = 'auto' | 'chalk' | 'sepia' | 'night';
export type Script = 'mushaf' | 'amiri' | 'scheherazade' | 'naskh';

export interface Prefs { mood: Mood; script: Script }

const MOODS: { id: Mood; name: string; note: string }[] = [
  { id: 'auto', name: 'Automatic', note: 'Chalk by day, Night when your device is dark' },
  { id: 'chalk', name: 'Chalk', note: 'Crimson on warm white' },
  { id: 'sepia', name: 'Sepia', note: 'Aged paper, browned ink' },
  { id: 'night', name: 'Night', note: 'Dark and soft, for reading at night' },
];

const SCRIPTS: { id: Script; name: string; family: string }[] = [
  { id: 'mushaf', name: 'Mushaf (King Fahd Complex)', family: '' },
  { id: 'amiri', name: 'Amiri Quran', family: "'Amiri Quran'" },
  { id: 'scheherazade', name: 'Scheherazade New', family: "'Scheherazade New'" },
  { id: 'naskh', name: 'Noto Naskh Arabic', family: "'Noto Naskh Arabic'" },
];

export const scriptFamily = (s: Script) => SCRIPTS.find((x) => x.id === s)?.family ?? '';

export function renderSettings(prefs: Prefs, change: (p: Partial<Prefs>) => void): HTMLElement {
  const root = h('div', { class: 'settings' });

  // --- theme
  const moods = h('div', { class: 'choices moods', role: 'radiogroup', 'aria-label': 'Theme' });
  for (const m of MOODS) {
    const b = h('button', { type: 'button', role: 'radio', class: 'choice', 'aria-checked': String(prefs.mood === m.id) },
      h('span', { class: `swatch swatch-${m.id}`, 'aria-hidden': 'true' }),
      h('span', { class: 'choice-text' }, h('span', { class: 'choice-name' }, m.name), h('span', { class: 'choice-note' }, m.note)));
    b.addEventListener('click', () => change({ mood: m.id }));
    moods.append(b);
  }

  // --- script for verse by verse
  const scripts = h('div', { class: 'choices', role: 'radiogroup', 'aria-label': 'Arabic script in verse by verse' });
  // The sample is real text from the added pages (the opening words of 14:1), never typed here.
  const sampleText = ayahWords('14:1').slice(1, 4).join(' ');
  for (const s of SCRIPTS) {
    const b = h('button', { type: 'button', role: 'radio', class: 'choice', 'aria-checked': String(prefs.script === s.id) },
      h('span', { class: 'choice-text' }, h('span', { class: 'choice-name' }, s.name),
        h('span', { class: 'choice-note' }, s.family ? 'Typed Arabic text' : 'The same letter shapes as the printed page')));
    if (s.family && sampleText) {
      const sample = h('span', { class: 'script-sample', lang: 'ar', dir: 'rtl' }, sampleText);
      sample.style.fontFamily = s.family;
      b.append(sample);
    }
    b.addEventListener('click', () => change({ script: s.id }));
    scripts.append(b);
  }

  root.append(
    section('Theme', moods),
    section('Arabic in verse by verse', scripts,
      h('p', { class: 'setting-note' }, 'The mushaf pages always use the official King Fahd Complex fonts, so they match print exactly.')),
    section('Your work', yourWork()),
    section('Recitations saved for offline', recitations()),
    ...(canWorkOffline() && !claudeHost() ? [section('Use without internet', offlineMushaf())] : []),
    section('Where the text comes from', sources()),
    h('p', { class: 'setting-note version' }, `Version: ${__BUILT__}`),
  );
  return root;
}

function section(title: string, ...body: HTMLElement[]): HTMLElement {
  return h('section', { class: 'setting' }, h('h2', { class: 'setting-title' }, title), ...body);
}

const SYNC_TEXT: Record<SyncState, { icon: 'cloud' | 'device'; text: string }> = {
  connecting: { icon: 'cloud', text: 'Connecting to your account…' },
  account: { icon: 'cloud', text: 'Saved to your Claude account. Your groups appear on every device where you open this link, and only you can see them.' },
  browser: { icon: 'device', text: 'Saved in this browser only. Download a backup to keep a copy or move it to another device.' },
};

export function syncLine(): HTMLElement {
  const s = SYNC_TEXT[syncState()];
  const p = h('p', { class: `sync-line sync-${syncState()}` });
  p.innerHTML = icon(s.icon);
  p.append(h('span', {}, s.text));
  return p;
}

export const countText = (count = editedCount()) =>
  count ? `You have changed the groups or written notes on ${count} ayah${count === 1 ? '' : 's'}.` : 'You haven’t changed any groups yet.';

function yourWork(): HTMLElement {
  const wrap = h('div', { class: 'work' });
  const count = editedCount();
  const status = h('p', { class: 'work-status', role: 'status' });
  wrap.append(syncLine(), h('p', { class: 'setting-note work-count' }, countText(count)));

  const actions = h('div', { class: 'work-actions' });
  const save = h('button', { type: 'button', class: 'btn' });
  save.innerHTML = `${icon('download')}<span class="label">Download backup</span>`;
  save.addEventListener('click', async () => { status.textContent = await downloadBackup(); });

  const file = h('input', { type: 'file', accept: '.json,application/json', id: 'restore-file', class: 'visually-hidden' }) as HTMLInputElement;
  const restore = h('label', { class: 'btn', for: 'restore-file' });
  restore.innerHTML = `${icon('upload')}<span class="label">Restore from backup</span>`;
  const confirm = h('div', { class: 'confirm', hidden: '' });

  file.addEventListener('change', async () => {
    const chosen = file.files?.[0];
    file.value = '';
    if (!chosen) return;
    const result = await readBackup(chosen);
    if ('error' in result) { status.textContent = result.error; confirm.hidden = true; return; }
    status.textContent = '';
    const yes = h('button', { type: 'button', class: 'btn solid' }, 'Restore');
    const no = h('button', { type: 'button', class: 'btn' }, 'Cancel');
    confirm.replaceChildren(
      h('p', {}, `This backup has your groups or notes for ${result.count} ayah${result.count === 1 ? '' : 's'}. Restoring replaces what’s here for those ayahs; everything else stays.`),
      h('div', { class: 'work-actions' }, yes, no));
    confirm.hidden = false;
    yes.addEventListener('click', () => { restoreBackup(result.notes); confirm.hidden = true; status.textContent = 'Restored.'; });
    no.addEventListener('click', () => { confirm.hidden = true; });
  });

  actions.append(save, restore, file);
  wrap.append(actions, confirm, status);
  return wrap;
}

function recitations(): HTMLElement {
  const wrap = h('div', { class: 'work' }, h('p', { class: 'setting-note' }, 'Loading…'));
  const fill = async () => {
    const list = await listDownloads();
    wrap.replaceChildren();
    if (!list.length) {
      wrap.append(h('p', { class: 'setting-note' }, 'None yet. To save a surah, tap Listen, choose the reciter and surah, then Download.'));
      return;
    }
    const total = list.reduce((a, d) => a + d.bytes, 0);
    wrap.append(h('p', { class: 'setting-note' }, `${list.length} saved, ${megabytes(total)} in all.`));
    const ul = h('ul', { class: 'downloads' });
    for (const d of list) {
      const del = h('button', { type: 'button', class: 'btn small' });
      del.innerHTML = `${icon('trash')}<span class="label">Remove</span>`;
      del.addEventListener('click', async () => { await deleteDownload(d.reciter, d.surah); void fill(); });
      ul.append(h('li', {},
        h('span', { class: 'download-name' }, `${getChapter(d.surah)?.name_complex ?? d.surah} · ${reciterById(d.reciter).name}`),
        h('span', { class: 'download-size' }, d.saved < d.total ? `${d.saved} of ${d.total} ayahs · ${megabytes(d.bytes)}` : megabytes(d.bytes)),
        del));
    }
    wrap.append(ul);
  };
  void fill();
  return wrap;
}

function offlineMushaf(): HTMLElement {
  const wrap = h('div', { class: 'work' });
  const note = h('p', { class: 'setting-note' }, 'Pages you open are kept for offline use as you go. You can also save all 604 pages at once (about 210 MB).');
  const status = h('p', { class: 'work-status', role: 'status' });
  const save = h('button', { type: 'button', class: 'btn' });
  save.innerHTML = `${icon('download')}<span class="label">Save the whole mushaf</span>`;
  save.addEventListener('click', async () => {
    save.setAttribute('disabled', '');
    const error = await saveMushaf((done, total) => { status.textContent = `Saving ${done} of ${total} files…`; });
    status.textContent = error ?? 'The whole mushaf is saved. It works with no internet.';
    save.removeAttribute('disabled');
  });
  wrap.append(note, h('div', { class: 'work-actions' }, save), status);
  mushafSaved().then(([have, all]) => {
    if (have >= all) status.textContent = 'The whole mushaf is saved. It works with no internet.';
    else if (have) status.textContent = `${Math.round((have / all) * 100)}% saved so far.`;
  }).catch(() => undefined);
  return wrap;
}

function sources(): HTMLElement {
  const list = h('ul', { class: 'sources' });
  for (const [what, from] of [
    ['Arabic', 'The official mushaf fonts of the King Fahd Complex, Madinah (one per page, unchanged).'],
    ['Page layout', 'Which word sits on which line: checked against the King Fahd Complex’s own listing and your printed mushaf.'],
    ['Translation', 'The Clear Quran by Dr. Mustafa Khattab, as on quran.com, unchanged.'],
    ['Groups', 'Suggested by matching each part of the translation to the Arabic words it means. Yours to change.'],
    ['Recitations', 'Per-ayah recordings from everyayah.com, played unchanged.'],
  ]) list.append(h('li', {}, h('span', { class: 'source-what' }, what), h('span', {}, from)));
  return list;
}
