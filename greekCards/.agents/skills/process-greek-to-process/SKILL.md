---
name: process-greek-to-process
description: Process Greek Anki cards imported from Quizlet in the `to_process` deck using AnkiConnect and the local README checklist. Use when the user asks to process, finish, translate, add Russian translations/examples to, or clean up Greek cards in Anki `to_process`, especially for the `Πες το ελληνικά` workflow.
---

# Process Greek `to_process`

## Required preflight

- Read `../README.md` relative to this skill folder, or `README.md` in the
  current project root if invoked from there.
- Treat the README section `Чеклист обработки to_process` as the source of
  truth. Do not start editing Anki until the checklist has been read.
- Use AnkiConnect for Anki work. Start with read-only actions such as
  `version`, `deckNames`, `findNotes`, and `notesInfo`.

## Scope and safety

- Work only with notes that are currently in deck `to_process`.
- Never edit cards or notes outside `to_process`.
- Never move cards out of `to_process`.
- Never delete notes, create notes, change decks, or rewrite tags unless the
  user explicitly asks for that separate operation.
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

## Workflow

1. Read the README checklist.
2. Connect to AnkiConnect and confirm API availability.
3. Read ids with `findNotes` for `deck:to_process`.
4. Fetch note details with `notesInfo`.
5. Filter out skipped cards: verb-form drills, already-processed cards, or
   ambiguous cases.
6. Process suitable notes using the README's `FrontText`, `BackText`,
   `[examples]...[/examples]`, highlight, reverse-card, and image rules.
7. Apply updates only with `updateNoteFields` and only to verified `to_process`
   note ids.
8. Read back updated notes with `notesInfo` to verify the fields.
9. Report what changed, what was skipped, and why.

## Batch behavior

If the user gives no batch size, process the suitable `to_process` notes in
manageable batches and continue while progress is reliable. Prefer skipping a
questionable card over guessing.
