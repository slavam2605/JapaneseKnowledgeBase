# Counter-reading lookup

Offline evidence collector for complete Japanese number/counter forms such as `七年`, `一本`, and
`何人`. It combines exact BCCWJ corpus frequencies, UniDic analysis, Open JTalk G2P, and exact
JMdict entries. It deliberately reports disagreements instead of choosing a reading silently.

## One-time setup

The source archives and checksums are documented in
`resources/counter_readings/SOURCES.md`.

```bash
python3 -m venv japaneseCards/.venv
japaneseCards/.venv/bin/python -m pip install \
  -r japaneseCards/requirements-counter-readings.txt
japaneseCards/.venv/bin/python \
  japaneseCards/tools/counter_readings_build_index.py
```

The generated `counter_readings_index.sqlite` is ignored by Git. BCCWJ is streamed directly from
its ZIP files when the index is built.

## Lookup

Full JSON evidence:

```bash
japaneseCards/.venv/bin/python \
  japaneseCards/tools/counter_readings.py 七年 一本 何年
```

Compact report:

```bash
japaneseCards/.venv/bin/python \
  japaneseCards/tools/counter_readings.py --summary 七年 一本 何年
```

Use `--fail-on-review` for a validation gate: the process exits with status 2 if a source is
missing or a plausible ambiguity remains.

For a counter family, always pass the complete `一`–`十` + `何` row in one invocation. The command
checks readings; the workflow separately enforces that all eleven cards are present in the draft.

## Anki preflight

`anki_add.py` automatically re-runs this lookup for every numeric-prefix expression in
`AiGeneratedJapaneseKanji`; this deliberately includes possible counters that are not yet in a
manual catalog. It additionally classifies counters from UniDic POS data plus the lexicalized
exceptions in `counter_reading_catalog.json`. The preflight runs for `--dry-run` too and rejects:

- incomplete local evidence;
- a `Kana` value absent from the plausible candidates (phonetic long-vowel variants are merged);
- `needs_review: true` without a recorded user decision.

After the user has resolved an ambiguous form, record that decision at the top level of the batch:

```json
"counter_reading_reviews": {
  "七年": {
    "kana": "ななねん",
    "reason": "пользователь выбрал частотный вариант после обсуждения"
  }
}
```

The review marker cannot override missing sources or admit an unsupported reading.

## Interpretation

- `*` / `plausible: true`: supported by UniDic, Open JTalk, JMdict, or the manually checked BCCWJ
  core corpus.
- `-` / `plausible: false`: visible corpus-only variant outside the core corpus. It is retained as
  evidence but does not by itself make the result ambiguous.
- `needs_review: true`: more than one plausible reading, disagreement between UniDic and Open
  JTalk, a strong unsupported corpus signal, missing evidence, or no plausible result.
- `BCCWJ` is an occurrence count, while `core` is the count in BCCWJ's manually checked core.
- `dominant` requires at least 20 total corpus occurrences and a frequency ratio of at least 5:1.
- Long-vowel spellings produced by pronunciation models (`とーか`) are merged with dictionary
  spellings (`とおか`) by their Open JTalk phoneme sequence.

The result is evidence, not a normative ruling. Semantic homographs such as `一日` still require the
intended meaning (date vs duration) before a card can be approved.
