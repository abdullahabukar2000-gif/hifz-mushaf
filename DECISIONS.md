# Answers to BUILD-SPEC §9

1. **Default translation:** the same one quran.com uses by default, The Clear Quran
   (Dr. Mustafa Khattab), resource 131. Check this ID against `/resources/translations`
   when translations are wired up in Phase 4.
2. **Hiding translations:** yes, flashcard-style. Tapping a phrase shows its translation;
   tapping again hides it.
3. **Pages:** support both a single page and a two-page spread. The spread is laid out
   like a real mushaf: odd page on the right, even page on the left.
4. **Progress:** yes, show memorisation progress, kept subtle (for example a small
   margin mark).
5. **Language:** keep explanations plain and simple.
6. **Data:** the 14:24–14:27 range in the spec was only an example of the user's own
   progress. Page contents always come from the quran.com API.

# Phase 2 findings (where the spec's assumptions didn't hold)

- **Lines are not pre-justified.** §2 says QCF V2 lines all measure ~15.3–16.1em. Measured
  on pages 255–262 they run 11.4–19.6em wide. Lines are therefore set flush to both
  margins (`space-between`, like print) in a 19.3em block, and the rare line wider than
  that is scaled down to fit (page 258 line 8: 95%). Short lines get wider word gaps.
- **Data source.** quran.com is blocked from the cloud build machine, so pages come from
  github.com/zonetecde/mushaf-layout (pinned). Every ayah's glyph codes are checked
  against the King Fahd Complex's own listing (`mushaf-v2.txt` in
  github.com/mustafa0x/qpc-fonts, pinned), and every page against its own font file.
  Page 254 fails that check (a glyph between 13:37 and 13:38 is missing from the
  GitHub data) and is left out.
- **Fonts are stored in the project**, unmodified, in `public/fonts/qcf2/`, not loaded
  from a CDN, because the app must work offline. Page fonts are `QCF2nnn.ttf`, the
  basmalah is `QCF2BSML.ttf`.
- **Juz and hizb** aren't in the margin yet: none of the reachable sources has a
  trustworthy table. The margins show the surah name and page number.
- **Surah headings** are a drawn frame with the name in Amiri Quran, since the
  heading-name glyphs in QCF2BSML aren't mapped yet.

# Phase 3 notes

- **Flashcard meanings (answer 2).** Tapping a phrase opens it with its meaning covered;
  tapping it again reveals the meaning, and again hides it.
- **Splitting lives in the phrase panel** for now: the ayah is shown word by word with a
  tap zone between each pair. Study mode (Phase 4) will add splitting inline.
- **Meaning and note can be typed in the panel** so the flashcard can be tried before
  study mode exists. Edits are kept in this browser only until Phase 4 saves them
  properly.
- **Phrase marks** are drawn in a layer behind the text: a 2px baseline rule in the
  phrase's tone (at half strength when not selected) and an 8% wash on the selected
  phrase. Checked at phone size: the Arabic reads the same marked or unmarked.
- **Example:** 14:24 comes pre-split as an example (breaks only, no meanings). It's
  labelled "example" until edited.

# After Phase 3 feedback

- **Colours removed** (user won't use them). The mushaf page shows no marks at rest;
  only the tapped phrase gets the 8% wash and baseline rule, in the accent.
- **Verse by verse view** (like quran.com's): each ayah in its mushaf glyphs, grouped
  into phrases, with The Clear Quran underneath. "Hide translations" covers them for
  recall; tap one to check. Switching views keeps your place.
- **Translation source:** The Clear Quran (Dr. Mustafa Khattab, "Allah" edition) from
  github.com/fawazahmed0/quran-api, pinned; wording matched quran.com for 14:22–23.
  Saved offline by `scripts/translations.js`.
- **Suggested grouping for every ayah** (`src/suggest.ts`): the mushaf's pause signs
  (ۖ ۗ ۘ ۚ) always end a phrase; longer stretches are cut into groups of about 3–5
  words, preferring cuts after an indefinite noun or before a clause opener, never
  after a small leaning word, and not between a noun and its adjective. It proposes
  boundaries only, never meanings. Once you edit an ayah, your grouping is saved and
  the suggestion no longer moves it; "use suggestion" goes back.
- **Editing groups:** in verse by verse, a faint dot sits between every two words
  (tap to split) and a bar between phrases (tap to join).
- **quran.com's page 258 differs** from the user's printed copy in its middle lines
  (e.g. where "أن دعوتكم" falls). The app follows the printed copy, which the user
  checked line by line.

# Phrase cards (after verse-by-verse feedback)

- **Verse by verse is now a stack of phrase cards** per ayah (inspired by the user's
  flashcard screenshot). Tap a card to fill in its English; tap again to hide it.
- **Card English is quran.com's word-by-word translation**, joined for the words in
  the card (repeated glosses shown once). Source: npm
  @kmaslesa/holy-quran-word-by-word-full-data@1.0.6, saved offline by
  `scripts/wordbyword.js`, which checks every ayah's word count matches ours. The
  full Clear Quran translation stays under each ayah.
- **Regrouping by dragging:** a grip between two cards; drag down to pull words up
  into the card above, up to push words down. Dragging a card to nothing joins the
  two. Arrow keys move one word at a time. "Split in two" on an open card.
- **Bottom buttons** are always visible now, in the accent colour, on a bar; the
  selected option is filled. (The spec's fade-away controls were too hard to see.)

# Boxes across the line (after card feedback)

- **Verse by verse flows horizontally again**, like quran.com: each phrase group sits in
  a box within the ayah's line, boxes wrapping naturally. No vertical card stack.
- **One English line per ayah, built box by box** from quran.com's word-by-word English.
  Tapping a box (or its part of the English) reveals or hides that box's part; a hidden
  part keeps its length as a pale blank. "Hide translations" sets whether parts start
  hidden. "Show the full sentence" swaps the line for The Clear Quran and back.
- **Regrouping:** drag the grip between two boxes left or right onto a word; the box
  before ends at that word. Dragging past a whole box joins the two. Double-tap a word
  to split its box after it. Arrow keys move a focused grip one word.
- Per-phrase meaning/note fields are no longer in verse by verse (they stay in the
  mushaf page's phrase panel).

# Mushaf page simplified (user: "get rid of the extra stuff")

- The mushaf view is now just the pages: every added page one after another, each
  filling the screen, scrolled vertically. No phrase panel, highlights, page-turn
  buttons or one/two-page switch.
- Verse by verse lists every added ayah in one scroll. Switching views keeps the page
  you were on.
- The per-phrase meaning/note fields are gone from the interface (stored notes are
  kept, unused). Controls: "verse by verse" / "mushaf page", and "hide translations"
  in verse view.

# Icons, horizontal mushaf, two pages, crimson

- **Accent is crimson** (#a3172f): ayah markers, buttons, open boxes, focus rings.
- **Every clickable control is a button with an icon** (inline line icons in
  `src/icons.ts`): next/previous, one/two pages, mushaf/verse by verse, hide/show
  translations, use suggestion, full sentence/box by box. On phones the bar becomes
  icon-over-label tabs.
- **The mushaf swipes horizontally**, one screen at a time, laid out right to left:
  the first page is on the right and the next arrives from the left, as when turning
  a printed mushaf. Arrow keys and the chevron buttons turn pages on desktop.
- **Two-page view is back** (odd page on the right). Hidden on phones, where the
  spread would be too small to read.
- Verse by verse stays a vertical scroll. Switching views or layouts keeps your page.

# Groups by meaning, one translation (after box-by-box feedback)

- **Suggested groups now follow the meaning** of The Clear Quran: each group of Arabic
  words is matched to the piece(s) of the published translation it means
  (`scripts/align-source.py` → `data/align/clear-quran.json`, 68 ayahs, 311 groups).
  The script checks the groups cover every Arabic word in order and that the pieces
  rebuild the translation exactly; the translation is never edited. Where English
  order differs, a group may own two separate pieces (e.g. 14:38 "Nothing … is hidden
  from Allah"). Ayahs without an alignment fall back to the pause-sign guess.
- **One translation line per ayah**, the published sentence in its own order. Tapping
  a box reveals or hides the piece(s) its words translate; tapping a piece does the
  same. If you regroup so a box covers only part of a meaning group, revealing it
  shows that whole piece (English can't be split finer than the alignment).
- The word-by-word English and the "full sentence / box by box" switch are gone
  (data, script and npm package removed).
- New ayahs need a line added to `scripts/align-source.py`; until then they use the
  fallback grouping and the translation reveals as a whole.

# Phase 4 and 5, and Home

- **Colours: Crimson #DC143C and Chalk #F2EFE7** (user's palette). Crimson text on
  chalk uses a deeper #B30F31 where #DC143C would be too light to read.
- **Themes (Phase 5):** Automatic (follows the device and the Claude viewer's dark
  mode), Chalk, Sepia (browned ink, deeper crimson), Night (#141310, ink at ~88%, a
  lifted crimson). Chosen in Settings; stored per browser.
- **Arabic in verse by verse:** the mushaf's own King Fahd glyphs (default), or typed
  text in Amiri Quran, Scheherazade New or Noto Naskh Arabic, all bundled for offline.
  The mushaf pages always use the King Fahd fonts; Settings says so.
- **Saving (Phase 4):** in the Claude link, groups and notes sync to one private
  document in the user's account (`data/users/<id>/notes`, readable only by them),
  merged newest-wins per ayah, pushed one write at a time after edits pause.
  Outside the viewer, or if the account isn't reachable, they stay in the browser.
  Resetting an ayah leaves a marker so the reset reaches other devices.
  Instead of files on disk via a dev server (the spec's plan), because the user only
  uses the link.
- **Backup:** Settings → Download backup (a .json file) and Restore from backup
  (checks it's a Hifz backup, asks before replacing, backup wins for the ayahs in it).
- **App shell:** a top bar (where you are; page-turn and two-page buttons in the
  mushaf, hide translations in verse by verse) and a bottom tab bar: Home, Mushaf,
  Verse by verse, Settings, each with an icon.
- **Home:** a crimson "Continue reading" card (last page, open in either view), your
  added surahs, then all 114 surahs with search; surahs not added yet are listed but
  dimmed.

# The whole Quran

- All 604 pages are in. `scripts/check-quran.js` walks all 6,236 ayahs across the pages
  and confirms each is present once with every word in order.
- 577 pages show in the King Fahd font. 27 pages (121–123, 144, 207, 532–534, 565, 568,
  570, 576, 584–593, 595–599) show typed Uthmani text instead, with a note on the page:
  their glyph codes or line positions couldn't be confirmed against the King Fahd listing,
  and a wrong glyph is wrong Qur'anic text. The basmalah still uses its own font there.
- Pages 1 and 2 have 8 lines, set in the middle of the page as in print.
- The app loads a small index first, then pages in files of 20 as you reach them. The
  mushaf keeps a place for every page but only draws those near the screen; verse by
  verse starts at your page and adds three pages at a time as you scroll, with a button
  for the pages before.
- Fonts (199 MB, unchanged TTFs) live in the artifact's file store, not in git.
- Home lists every surah with its ayah count and the page it starts on.
- Meaning groups matched to the translation still exist only for pages 255–262. Every
  other ayah uses the pause-sign guess, and its translation shows whole.

# Meaning blocks for every surah

- `scripts/align-auto.py` matches each Arabic word to its part of The Clear Quran using
  quran.com's word-by-word English (npm `@kmaslesa/holy-quran-word-by-word-full-data`,
  matched by word position). The translation is only ever sliced, never reworded.
- Safety rule: if any word in a block clearly belongs to another block, the two join.
  A doubtful match makes a bigger block, never a block with the wrong English.
- Result: 4,603 of 6,236 ayahs have blocks (3.8 per ayah). About 1,630 still reveal
  whole, mostly very short ayahs. 13:43–15:15 keep the hand-checked groups
  (`align-source.py` → `data/align/hand.json`).
- Plan for hand-checking: one surah at a time, correcting only the blocks that are off,
  starting with the surahs being memorised.

# Website, home-screen app, recitation

- The app is published as a website on GitHub Pages by `.github/workflows/pages.yml` on
  every push. Fonts are fetched at build time by `scripts/fetch-fonts.js` from the pinned
  source and checked against `data/font-hashes.json` (sha256), so they stay out of git.
- Home-screen app: `public/manifest.webmanifest`, icons in `public/icons/`, and a service
  worker (`public/sw.js`) that keeps the app and every page you've opened for offline use.
  Settings can save the whole mushaf at once (~210 MB).
- Recitation: everyayah.com per-ayah MP3s (quranicaudio.com mirror as backup) for
  Alafasy, Husary, Minshawi (murattal), Maher Al-Muaiqly, Khalifa Al-Tunaiji. Mansour
  As-Salimi is left out: no per-ayah source could be confirmed.
- Nothing downloads on its own. A surah is saved for a reciter only when you tap
  Download; saved recordings play with no connection. Settings lists and removes them.
- Repeat each ayah (1–10 or always), repeat the range, speed 0.5–1.5×, optional quiet
  after each ayah. Surahs other than 1 and 9 start with the basmalah (Al-Fatihah's first
  ayah recording) when the range starts at ayah 1.
- Recitation check (scripts/check-audio*.py, run on GitHub Actions): every file's length
  compared with the ayah lengths and with other reciters, across the whole Quran. All five
  reciters are numbered correctly except Khalifa Al-Tunaiji's Surah Ibrahim: files 1–50
  hold ayahs 2–51, file 51 repeats 51, file 52 is 52, and 14:1 is missing. The app maps
  those (FILE_FIXES in src/recite.ts), says 14:1 is missing and skips it, and clears any
  copies saved before the fix.

# Bigger mushaf, Abdirashid Sufi

- Mushaf page ~10% bigger: on phones the page now uses the full width (side margin
  0.2em, 8px gutter); line spacing 1.8em (was 1.9) and smaller page margins everywhere.
- Abdirashid Ali Sufi (Hafs) isn't on everyayah; his Hafs recitation on quranicaudio.com
  is one file per surah. Ayah times come from the Quran Android app's timing database
  (android.quran.com/data/databases/audio/abdurrashid_sufi.zip), fetched and checked at
  build time by scripts/fetch-timings.py (all 114 surahs complete; lengths match the
  ayahs). The player seeks to each ayah's start and stops at its end; straight-through
  listening just keeps playing. Downloading a surah saves its one file.

# Recitation mode: removed

- The microphone recitation checker (and its speech model, onnxruntime and test
  workflow) was removed at the user's request.

# Reveal as recited

- One button (mushaf and verse by verse) hides the Arabic (each word a pale blank of the
  same size; ayah numbers, surah names and the basmalah stay) and covers the translation.
  While a reciter plays, each word shows as it's recited and each meaning group opens as
  its first word is reached. Press it again to show everything. On the mushaf page a
  blank can be tapped to peek.
- Word times: for Mishary Alafasy, Mahmoud Khalil Al-Husary and Minshawi (murattal),
  scripts/fetch-qdc.py fetches quran.com's recordings' ayah and word timings at build
  time (checked: every ayah's words numbered 1..n as in the mushaf, ayahs in order), and
  the app then plays those recordings (one file per surah), so words follow exactly. If
  the data isn't there, those reciters fall back to their everyayah per-ayah files.
  Other reciters: word positions are estimated from the words' lengths.

# Khalifa Al-Tunaiji from quran.com

- everyayah's Tunaiji files have ayahs under the wrong numbers in places (Ibrahim was
  mapped by hand; Ar-Ra'd was reported off too). He now plays from quran.com's
  whole-surah recordings, timed by ayah (scripts/fetch-qdc.py). At build time every
  surah's ayah lengths are compared with Husary's and Minshawi's; a surah that
  disagrees with both is reported, and if more than 3 do, Tunaiji is left on the old
  files. His word timings there are too coarse, so his words use the estimate.

# Layout

- Verse by verse is centred (Arabic lines and English). The surah name sits in the
  middle of its frame. On wide screens the top and bottom bars line up with the page.

# Smaller meaning boxes; no sideways scrolling

- scripts/align-auto.py cuts the translation finer (pieces over 3 words are cut again
  before a preposition, "of", "that", "the", an auxiliary verb...), and joins two groups
  far apart only on two separate clues (one loose match, like "protecting" and
  "protector", used to merge everything in between into one huge box). Ar-Ra'd: boxes
  average 3.2 words (was 4.3), biggest 24 (was 35); whole Quran: biggest 63 (was 120).
  Pieces are still exact slices of the translation; the hand-checked groups are kept.
- A box too long for the screen wraps inside itself; verse by verse can't scroll sideways.

# Reveal choices; word timings by listening

- The reveal button opens a menu: show everything; reveal the translation (the Arabic
  stays); reveal Arabic and translation.
- Word timings for reciters without quran.com's (Abdirashid Sufi, Maher Al-Muaiqly,
  Muhammad Ayyub, Khalifa Al-Tunaiji, and the ayahs missing from quran.com's for the
  others) come from listening to the recordings: .github/workflows/align-words.yml runs
  scripts/align-words.py over every ayah on GitHub Actions. Tilawi's speech model hears
  the ayah; the letters it hears (harakat and marks set aside) are lined up with the
  mushaf's own words, and each word starts when its first letter is heard. Each ayah is
  scored by the share of its letters heard; scripts/merge-words.py uses those at 0.8 or
  above at build time, and the app estimates only for the rest. Results are committed in
  data/words-aligned/. First try (CTC forced alignment to the model's token table) failed:
  the model often writes harakat, the table has none.

# Ayah starts checked by listening (quran.com recordings)

quran.com's published ayah times are off in places (Minshawi's Ar-Ra'd starts
~10 s early, so an ayah began with the previous one's ending; Tunaiji's Yunus,
Ar-Ra'd and Al-Jinn drift; his Ibrahim has none). `scripts/retime-surah.py`
listens to each whole-surah file (Tilawi FastConformer) and checks every
published start: it is kept when the ayah's opening letters are heard there,
and moved only when the opening is heard close by — forward when what comes
before it is the previous ayah's ending (or a short pause), back by at most
5 s. This keeps it off look-alike openings elsewhere in the surah. Only where
there are no published times is the start found by listening alone.
`scripts/apply-retimed.py` applies the results at build time. Tunaiji 14:37's
opening fell where two listening chunks meet; its start was set by hand just
after 14:36's last letter (noted in its file as `by_hand`).

Where that ayah-by-ayah check still left a start wrong (Minshawi's Ar-Ra'd:
13:4, 13:21 and 13:28 began inside the ayah before; 13:35-36 a second early),
`scripts/resync-surah.py` lines up the whole surah's letters with everything
heard in one go, so each ayah can only land after the one before it, and
writes every ayah's word times from the same match (quran.com's word times
there were off along with its ayah times). Every ayah was then checked to
open with its own first word and end with its own last.

# Ar-Ra'd meaning boxes by hand

All of Ar-Ra'd (13:1-42; 13:43 already was) now has hand-made groups in
`scripts/align-source.py`: each box is one small unit of meaning (a subject,
an action, a phrase such as "from your Lord"), paired with exactly the Arabic
words it translates, so a box can be tied back to its words while memorising.
Where English order differs from the Arabic, a box takes the separate
pieces of its meaning (e.g. 13:3 "and created … in pairs"). Pieces are exact
slices of The Clear Quran, never reworded; the script checks they rebuild
each ayah's translation. During recitation a box shows as its first Arabic
word is reached.
