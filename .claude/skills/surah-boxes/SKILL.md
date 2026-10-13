---
name: surah-boxes
description: Rework one surah for verse-by-verse study in the Hifz Mushaf app — hand-made meaning boxes (each a single unit of meaning tied to exactly its Arabic words) and overview notes on what each group of ayahs is about. Use when the user names a surah ("do Surah Yusuf", "/surah-boxes 12").
---

# Surah boxes and overview notes

The user names a surah (by name or number). Do all of the below for that
surah, then build, commit, push, and report in plain words with 2–3 examples.
The user is not technical: no jargon in the report.

## Rules that never bend

- Never type Qur'anic text or write a translation. English pieces are exact
  slices of The Clear Quran (`data/translations/clear-quran/`), never reworded,
  and together they must rebuild each ayah's translation (the script checks).
- Arabic word indexes come from the app's mushaf (`data/pages/`), 0-based.
  The glosses can merge or split words: when the worksheet warns the counts
  differ, line them up by meaning (e.g. بَعْدَ مَا is two mushaf words, one gloss).
- Overview notes are the app's own study notes (summaries of what a group of
  ayahs is about), never presented as translation. Keep them factual and
  plain; if unsure what a passage covers, say less, not more.

## 1. Worksheet

```
python3 scripts/box-worksheet.py <surah> [<path>/data.json]
```
If `node_modules/@kmaslesa/holy-quran-word-by-word-full-data` is missing,
`npm pack @kmaslesa/holy-quran-word-by-word-full-data` in the scratchpad, untar
into its own empty folder, and pass `package/data.json`.

## 2. Meaning boxes — what a good box is

The aim: the user taps a box and links a small group of Arabic words to one
meaning, to memorise the surah and become fluent in Qur'anic Arabic, while
still following the story.

- **One idea per box.** Split at every clause: who acts / what they do /
  to whom / where / when / why. "whether any of you" | "speaks secretly" |
  "or openly," — not one box for all three.
- **Usually 1–4 Arabic words.** A box over ~5 words is almost always several
  ideas: split it. Keep together only what means nothing apart
  (يَٰٓأَيُّهَا ٱلَّذِينَ ءَامَنُوا, a name with its title, a fixed phrase).
- **Learnable units:** a verb with its pronoun, a noun with its adjective or
  possessive, a preposition with its object (مِن رَّبِّكَ "from your Lord"),
  each item of a list on its own (parents | spouses | descendants).
- **Follow the story:** boxes read in order should still tell what happens;
  speech openers ("Say,", "They said,") get their own box.
- **English order ≠ Arabic order:** give a box several pieces
  (`[end, ["and created", "in pairs."]]`) rather than merging boxes.
  Where the English can't be cut cleanly, accept one slightly larger box and
  mention it in the report.
- A box reveals when the reciter reaches its first Arabic word, and tapping it
  shows its own English — so every piece must sit with the words it translates.

Write `data/boxes/<surah>.json`:
```json
{"12:1": [[0, "Alif-Lãm-Ra."], [3, "These are the verses of the clear Book."]],
 "12:2": [[1, "Indeed, We have sent it down"], [3, ["as an Arabic Quran", "so that"]], ...]}
```
(`[last word index, piece or [pieces]]`; groups cover every word in order.)
Then:
```
python3 scripts/align-source.py            # must print "ok"; fix every problem it lists
python3 scripts/align-auto.py <data.json> --write
```
Check that only this surah's ayahs changed in `data/align/clear-quran.json`
(compare with a copy taken before), and print each ayah's boxes once to
re-read them against the rules above before committing.

## 3. Overview notes

Write `data/notes/<surah>.json`:
```json
{"note": "Overview notes written for this app as a study aid; not the translation.",
 "sections": [[1, 3, "The Quran revealed in Arabic; the best of stories."],
              [4, 6, "Yusuf's dream of eleven stars, the sun and the moon; his father's warning."]]}
```
- Sections cover the whole surah in order, no gaps or overlaps; a new section
  wherever the topic or the story turns (new scene, new speaker, from story to
  lesson).
- Each note is one or two short sentences: what happens / what it teaches.
- They show before the first ayah of each section in verse by verse (in the
  margin on wide screens), with the ayah range.

## 4. Finish

- `npx tsc --noEmit -p . && npx vite build`
- Add a short line to DECISIONS.md if anything about the approach changed.
- Commit (`<Surah>: meaning boxes by hand and overview notes`), push to the
  working branch, and tell the user how many boxes it has now, give examples
  (Arabic → English), list the sections, and remind them to close and reopen
  the site once it's live.
