---
name: sync-greek-reciprocal-ne
description: Synchronize missing reverse Greek Anki `(не …)` clarifications from the current `to_process` deck into `Πες το ελληνικά` using AnkiConnect. Use after the user has manually reviewed `to_process` and asks to add or synchronize reciprocal `(не …)` links; do not use it to process or translate the temporary cards themselves.
---

# Sync Greek reciprocal `(не …)` links

Read `greekCards/README.md` first. Its section “Синхронизация обратных
`(не …)`” is the source of truth.

## Scope and safety

- Treat the current cards in `to_process` as the only source of relations. For
  each `A (не B)` there, add a missing `(не A)` only to an unambiguous existing
  card `B` in `Πες το ελληνικά`.
- Do not edit `to_process`. Do not create, delete, move, or retag its notes.
- Do not remove or rewrite old reverse markers in the primary deck. A marker
  absent from current `to_process` may be manual; report a requested cleanup
  separately and wait for explicit approval before removing anything.
- Do not use embedding similarity to infer a relation. Resolve targets from
  the written `(не …)` terms only; skip not-found or ambiguous targets.
- Preserve every existing primary-card marker. Merge a new term into the
  existing list, for example `(не απουσιάζω)` plus `φεύγω` becomes
  `(не απουσιάζω, φεύγω)`.

## Procedure

1. Use AnkiConnect read-only calls (`version`, `deckNames`, `findNotes`,
   `notesInfo`) to confirm that both decks are available.
2. Refresh the local snapshots without changing Anki:

   ```bash
   python3 greekCards/scripts/export_anki_notes.py --deck "Πες το ελληνικά"
   python3 greekCards/scripts/export_anki_notes.py --deck to_process
   ```

3. Produce and inspect a dry-run report:

   ```bash
   greekCards/.venv/bin/python greekCards/scripts/sync_reciprocal_ne.py \
     --report greekCards/data/reciprocal-ne-sync-YYYY-MM-DD.md
   ```

   Confirm that each planned relation comes from a current source card and that
   the target resolution is unique. Keep skipped targets in the report.
4. Only after reviewing the report, apply the plan with the same command plus
   `--apply`. The script rechecks each target's primary-deck membership,
   updates only `BackText`, adds `ai_generated::to_review` without removing
   existing tags, and reads the result back through `notesInfo`.
5. Report the changed primary notes, skipped sources, and any errors. Verify
   that every changed note has the intended merged `(не …)` marker and the
   review tag.
