# Japanese Cards

This directory contains the Japanese Anki-card workflow. Treat it as a separate domain from the
Kotlin application and from `greekCards/`.

## Start Here

- Read `README.md` first; it is the map of the directory and explains which files are authoritative.
- Before any Anki write operation, read `knowledge/conventions.md` in full.
- Read `STATUS.md` when the task depends on what has already been added to Anki, and update it after
  creating a batch of cards.
- Paths such as `data/...`, `knowledge/...`, and `tools/...` in Japanese-card instructions are
  relative to `japaneseCards/` unless the instruction gives a repository-root path explicitly.

## Workflows

Use the matching repository skill from the repository-root `.agents/skills/`:

- `process-inbox` — classify `data/inbox.md` and answer language questions.
- `japanese-cards` — create word, kanji-reading, and grammar cards.
- `process-remarks` — apply corrections from the Anki `Remarks` field.
- `mnn-extract` — extract Minna no Nihongo vocabulary into the reference catalog.
- `dedup-cards` — compare new cards with the archive and process duplicates safely.

The skills define procedures; files under `knowledge/` define card content and safety rules. When
they overlap, follow the relevant `knowledge/` file and keep duplicated guidance out of the skill.
