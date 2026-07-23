---
name: process-greek-to-process
description: Process Greek Anki cards imported from Quizlet in the `to_process` deck using AnkiConnect and the local README checklist. Use when the user asks to process, finish, translate, add Russian translations/examples to, or clean up Greek cards in Anki `to_process`, especially for the `Πες το ελληνικά` workflow. Retrieve embedding neighbours when deciding whether a card needs a `(не …)` clarification, but never add one from similarity score alone.
---

# Process Greek `to_process`

## Required preflight

- Read `greekCards/README.md` from the repository root.
- Treat the README section `Чеклист обработки to_process` as the source of
  truth. Do not start editing Anki until the checklist has been read.
- Use AnkiConnect for Anki work. Start with read-only actions such as
  `version`, `deckNames`, `findNotes`, and `notesInfo`.

## Scope and safety

- Work only with notes that are currently in deck `to_process`.
- Never edit cards or notes outside `to_process`.
- Never move cards out of `to_process`.
- Never delete notes, create notes, change decks, or rewrite tags. For a
  confirmed `to_process` duplicate, append `to_remove`; never remove existing
  tags.
- Skip verb-form cards where both sides are Greek verbs/forms in different
  tenses.
- If a note's deck membership is ambiguous, skip it.
- If a card is already fully processed, skip it unless the user asks for a
  revision.

## Editing rules

- Preserve the existing note type and fields.
- Usually edit only `BackText`; adjust `FrontText` only for clear Greek spelling,
  article, or form issues that the README rules cover.
- Preserve Quizlet English unless it is clearly wrong.
- Add Russian translation and examples according to the README format.
- Do not touch `Image` if the imported image is suitable.
- Leave `Add Reverse` as-is by default. Remove it only for longer, complex Greek
  phrases that are genuinely ambiguous to produce from Russian; when unsure,
  leave it for the user to decide.
- Before any `updateNoteFields` call, verify that the note id came from
  `findNotes` with query `deck:to_process`.

## Duplicates

- Check every `to_process` note against `Πες το ελληνικά` before translating,
  generating examples, or considering `(не …)`.
- First compare normalized front terms: ignore case, accents, and a leading
  Greek article; compare each listed form separately. Thus `η μιλιά` = `μιλιά`,
  `δεν βλέπω την ώρα` = `Δεν βλέπω την ώρα`, and
  `μεγάλος, μεγάλη, μεγάλο` duplicates `μεγάλος`.
- Use embedding neighbours only to discover candidates. Mark a duplicate only
  after confirming the same lexical item or phrase; never do so for a synonym
  or topical neighbour. Compare the central `BackText` meaning too: identical
  spelling with another sense, such as a physically inflated object versus an
  inflated price, is not a duplicate.
- For a confirmed duplicate, prepend
  `(дубликат <FrontText основной карточки>)<br>` to `BackText`, append the
  `to_remove` tag, preserve all existing content and tags, verify the note, and
  skip every other processing step for it. Never delete or move the note.

## Embedding candidates for `(не …)`

- Follow the README section `Уточнения (не …) и embedding-кандидаты`; its
  selection rule overrides any intuition based on a score.
- At the start of a batch, refresh the local export of `Πες το ελληνικά`, build
  its incremental local embeddings, and export `to_process` using the commands
  in the README. These actions do not edit Anki.
- For each suitable `to_process` note, run:

  ```bash
  greekCards/.venv/bin/python greekCards/scripts/search_similar.py \
    --backend local \
    --query-deck to_process \
    --deck "Πες το ελληνικά" \
    --note-id <verified-note-id> \
    --top 10 \
    --format markdown
  ```

- Treat the ten results as candidates to assess. Add `(не …)` only for a
  useful, genuinely confusable alternative in the same Russian context; reject
  thematic, derivational, or merely component-level neighbours. Do not infer a
  contrast from a shared word or root when the central meanings differ:
  `έχω γερά νεύρα` and `έχω νεύρα` are not a `(не …)` pair. A phrase fragment
  is valid when it is the distinguishing part of a longer expression.
- If no candidate clearly qualifies, do not add a `(не …)` note. Preserve an
  existing valid clarification unless the user requests its revision.
- Never replace an existing `(не …)` list when adding a new target. Merge the
  new target into it and retain every old one: `(не απουσιάζω)` plus `φεύγω`
  becomes `(не απουσιάζω, φεύγω)`, never `(не φεύγω)`.
- Do not add or change reverse `(не …)` markers in `Πες το ελληνικά`. After the
  user reviews `to_process`, the separate `$sync-greek-reciprocal-ne` skill
  derives and adds missing reverse markers from the then-current source notes.

## Workflow

1. Read the README checklist.
2. Connect to AnkiConnect and confirm API availability.
3. Refresh the local embedding data for the batch as described above.
4. Read ids with `findNotes` for `deck:to_process`.
5. Fetch note details with `notesInfo`.
6. Detect confirmed duplicates, mark them `to_remove`, and skip them.
7. Filter out other skipped cards: verb-form drills, already-processed cards, or
   ambiguous cases.
8. Get top-10 embedding candidates and decide on `(не …)` according to the
   README rule before composing `BackText`.
9. Process suitable notes using the README's `FrontText`, `BackText`,
   `[examples]...[/examples]`, highlight, reverse-card, and image rules.
10. Apply updates only with `updateNoteFields` and only to verified `to_process`
   note ids.
11. Read back updated notes with `notesInfo` to verify the fields.
12. Report what changed, what was skipped, and why.

## Batch behavior

If the user gives no batch size, process the suitable `to_process` notes in
manageable batches and continue while progress is reliable. Prefer skipping a
questionable card over guessing.
