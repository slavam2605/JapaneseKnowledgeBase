#!/usr/bin/env python3
"""Report kanji-reading cards that are not covered by the words deck.

The scanner is deliberately read-only with respect to both Anki and the
SQLite index.  It has two independent stages:

1. A deterministic stage proves coverage only when both the written form and
   its reading occur in a word/phrase card.  For example, ``電気`` / ``でんき``
   is covered by ``電気をつける`` / ``でんきをつける``.
2. Only the remaining cards are compared using the already-stored embeddings.
   Their best word-card neighbours form a compact ``REVIEW_SEMANTIC`` queue
   for an LLM or a person.  Semantic similarity is never accepted as proof of
   coverage, so unrelated synonyms cannot hide a missing word.

Before running, refresh the two decks in the local index and build their
embeddings.  See EMBEDDINGS.md for the two commands.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from embedding_utils import (
    DEFAULT_BACKEND,
    DEFAULT_DB_PATH,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    compact_text,
    cosine_similarity,
    dimension_key,
    embedding_model_key,
    unpack_vector,
)


DEFAULT_WORDS_DECK = "新日本語::Слова"
DEFAULT_KANJI_DECK = "新日本語::Чтение кандзи"
DEFAULT_WORDS_NOTE_TYPE = "AiGeneratedJapaneseWords"
DEFAULT_KANJI_NOTE_TYPE = "AiGeneratedJapaneseKanji"
DEFAULT_KANJI_TAG = "to_review"
DEFAULT_TOP = 3
DEFAULT_REVIEW_THRESHOLD = 0.80
DEFAULT_JSON_OUT = Path(__file__).resolve().parent.parent / "data" / "kanji_word_coverage.json"
DEFAULT_REVIEW_OUT = Path(__file__).resolve().parent.parent / "data" / "kanji_word_coverage_review.md"


class CoverageError(RuntimeError):
    pass


@dataclass(frozen=True)
class IndexedNote:
    note_id: int
    deck_name: str
    front: str
    meaning: str
    written: str
    reading: str
    vector: list[float]
    vector_norm: float


def contains_han(text: str) -> bool:
    return any("一" <= ch <= "鿿" or "㐀" <= ch <= "䶿" for ch in text)


def normalize_surface(text: str) -> str:
    """Normalize a field value while retaining the Japanese word surface."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(
        ch
        for ch in text
        if (
            "぀" <= ch <= "ヿ"
            or "一" <= ch <= "鿿"
            or "㐀" <= ch <= "䶿"
            or ch in "々〆ヵヶー"
            or ch.isdecimal()
        )
    )


def normalize_reading(text: str) -> str:
    """Normalize a reading; katakana and hiragana compare as the same text."""
    folded: list[str] = []
    for ch in normalize_surface(text):
        if 0x30A1 <= ord(ch) <= 0x30F6:
            ch = chr(ord(ch) - 0x60)
        folded.append(ch)
    return "".join(folded)


def parse_terms(raw_terms: str, front: str) -> tuple[str, str]:
    """Return (written form, reading) from the exporter's front_terms_json.

    The exporter writes terms in the order ``Kanji``, then ``Kana`` and removes
    duplicates.  A kana-only card therefore has one term, which correctly
    serves as both written form and reading.
    """
    try:
        parsed = json.loads(raw_terms)
    except json.JSONDecodeError as error:
        raise CoverageError(f"Invalid front_terms_json for {front!r}: {error}") from error
    if not isinstance(parsed, list):
        raise CoverageError(f"front_terms_json for {front!r} is not a JSON list.")

    terms = [str(term) for term in parsed if isinstance(term, str) and term.strip()]
    if not terms:
        terms = [front]

    written = normalize_surface(terms[0])
    reading_source = terms[1] if len(terms) > 1 else terms[0]
    reading = normalize_reading(reading_source)
    if not written or not reading:
        raise CoverageError(f"Could not derive written form and reading for {front!r}.")
    return written, reading


def has_tag(raw_tags: str, tag: str) -> bool:
    try:
        parsed = json.loads(raw_tags)
    except json.JSONDecodeError as error:
        raise CoverageError(f"Invalid tags_json: {error}") from error
    if not isinstance(parsed, list):
        raise CoverageError("tags_json is not a JSON list.")
    if "::" in tag:
        return tag in parsed
    return any(existing_tag == tag or existing_tag.endswith(f"::{tag}") for existing_tag in parsed)


def connect_read_only(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise CoverageError(f"Index database does not exist: {db_path}")
    connection = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def load_indexed_notes(
    connection: sqlite3.Connection,
    deck: str,
    note_type: str,
    embedding_model: str,
    embedding_dimension: str,
    required_tag: str | None = None,
) -> list[IndexedNote]:
    rows = list(
        connection.execute(
            """
            SELECT
                n.note_id,
                n.deck_name,
                n.front_clean,
                n.back_clean,
                n.front_terms_json,
                n.tags_json,
                n.embedding_hash,
                e.vector_blob,
                e.vector_norm,
                e.source_content_hash
            FROM anki_notes n
            LEFT JOIN note_embeddings e
              ON e.deck_name = n.deck_name
             AND e.note_id = n.note_id
             AND e.embedding_model = ?
             AND e.dimension_key = ?
            WHERE n.deck_name = ?
              AND n.model_name = ?
              AND n.is_present = 1
            ORDER BY n.note_id
            """,
            (embedding_model, embedding_dimension, deck, note_type),
        )
    )
    if not rows:
        raise CoverageError(f"No present {note_type!r} notes in deck {deck!r}.")

    if required_tag is not None:
        rows = [row for row in rows if has_tag(str(row["tags_json"]), required_tag)]
        if not rows:
            return []

    missing_embeddings = [
        row
        for row in rows
        if row["vector_blob"] is None or row["source_content_hash"] != row["embedding_hash"]
    ]
    if missing_embeddings:
        examples = ", ".join(str(row["note_id"]) for row in missing_embeddings[:5])
        raise CoverageError(
            f"{len(missing_embeddings)} notes in {deck!r} have no current embedding "
            f"for {embedding_model!r} / {embedding_dimension!r} (for example: {examples}).\n"
            f"Refresh the deck with export_anki_notes.py, then run build_embeddings.py --deck {deck!r}."
        )

    notes: list[IndexedNote] = []
    for row in rows:
        front = str(row["front_clean"])
        written, reading = parse_terms(str(row["front_terms_json"]), front)
        notes.append(
            IndexedNote(
                note_id=int(row["note_id"]),
                deck_name=str(row["deck_name"]),
                front=front,
                meaning=str(row["back_clean"]),
                written=written,
                reading=reading,
                vector=list(unpack_vector(row["vector_blob"])),
                vector_norm=float(row["vector_norm"]),
            )
        )
    return notes


def exact_matches(kanji_note: IndexedNote, word_notes: list[IndexedNote]) -> list[IndexedNote]:
    return [
        word_note
        for word_note in word_notes
        if kanji_note.written == word_note.written and kanji_note.reading == word_note.reading
    ]


def phrase_matches(kanji_note: IndexedNote, word_notes: list[IndexedNote]) -> list[IndexedNote]:
    """Find longer word expressions which contain this exact written/reading pair.

    A single-character target is intentionally excluded.  ``月`` in ``月曜日``
    may be a different lexical reading despite sharing a character; it belongs
    in the semantic/manual-review queue instead of being accepted automatically.
    """
    if len(kanji_note.written) < 2:
        return []
    matches = [
        word_note
        for word_note in word_notes
        if (
            kanji_note.written != word_note.written
            and kanji_note.written in word_note.written
            and kanji_note.reading in word_note.reading
        )
    ]
    return sorted(matches, key=lambda note: (len(note.written), note.note_id))


def semantic_matches(
    kanji_note: IndexedNote,
    word_notes: list[IndexedNote],
    top: int,
) -> list[tuple[float, IndexedNote]]:
    matches = [
        (
            cosine_similarity(
                kanji_note.vector,
                kanji_note.vector_norm,
                word_note.vector,
                word_note.vector_norm,
            ),
            word_note,
        )
        for word_note in word_notes
    ]
    return sorted(matches, key=lambda item: (-item[0], item[1].note_id))[:top]


def match_payload(match: IndexedNote, kind: str, score: float | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind,
        "note_id": match.note_id,
        "front": match.front,
        "meaning": match.meaning,
    }
    if score is not None:
        payload["cosine"] = round(score, 4)
    return payload


def scan(
    kanji_notes: list[IndexedNote],
    word_notes: list[IndexedNote],
    top: int,
    review_threshold: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for kanji_note in kanji_notes:
        payload: dict[str, Any] = {
            "kanji": {
                "note_id": kanji_note.note_id,
                "front": kanji_note.front,
                "meaning": kanji_note.meaning,
            }
        }
        exact = exact_matches(kanji_note, word_notes)
        if exact:
            payload["status"] = "COVERED_EXACT"
            payload["matches"] = [match_payload(match, "exact") for match in exact]
            results.append(payload)
            continue

        phrase = phrase_matches(kanji_note, word_notes)
        if phrase:
            payload["status"] = "COVERED_IN_PHRASE"
            payload["matches"] = [match_payload(match, "phrase") for match in phrase]
            results.append(payload)
            continue

        semantic = semantic_matches(kanji_note, word_notes, top)
        payload["matches"] = [
            match_payload(match, "semantic", score) for score, match in semantic
        ]
        top_score = semantic[0][0] if semantic else 0.0
        payload["status"] = (
            "REVIEW_SEMANTIC" if top_score >= review_threshold else "MISSING"
        )
        results.append(payload)
    return results


def summary(results: list[dict[str, Any]]) -> dict[str, int]:
    statuses = [
        "COVERED_EXACT",
        "COVERED_IN_PHRASE",
        "REVIEW_SEMANTIC",
        "MISSING",
    ]
    return {status: sum(result["status"] == status for result in results) for status in statuses}


def write_review(
    path: Path,
    results: list[dict[str, Any]],
    counts: dict[str, int],
    review_threshold: float,
    kanji_tag: str | None,
) -> None:
    scope = f"tag:{kanji_tag}" if kanji_tag is not None else "all present kanji notes"
    lines = [
        "# Покрытие: чтение кандзи → слова",
        "",
        "Сканер ничего не меняет в Anki. `COVERED_*` подтверждены формой и чтением; "
        "эмбеддинги формируют только очередь `REVIEW_SEMANTIC`.",
        f"Область проверки: `{scope}`.",
        "",
        f"- Всего карточек чтения: {len(results)}",
        f"- Точное покрытие: {counts['COVERED_EXACT']}",
        f"- Покрытие внутри выражения: {counts['COVERED_IN_PHRASE']}",
        f"- Проверить LLM/вручную (cos ≥ {review_threshold:.2f}): {counts['REVIEW_SEMANTIC']}",
        f"- Нет убедительного кандидата: {counts['MISSING']}",
        "",
    ]

    review = [result for result in results if result["status"] == "REVIEW_SEMANTIC"]
    lines += [
        f"## Очередь LLM / ручной проверки ({len(review)})",
        "",
        "Смысловая близость **не означает** покрытие. Признавать пару покрытой можно, "
        "только если слово из колоды слов действительно учит ту же запись/чтение.",
        "",
        "| Чтение кандзи | Значение | Лучшие кандидаты из слов |",
        "|---|---|---|",
    ]
    for result in review:
        kanji = result["kanji"]
        candidates = "<br>".join(
            f"{match['cosine']:.4f} — {compact_text(match['front'], 48)} "
            f"({compact_text(match['meaning'], 48)})"
            for match in result["matches"]
        )
        lines.append(
            f"| {compact_text(kanji['front'], 48)} | {compact_text(kanji['meaning'], 60)} "
            f"| {candidates} |"
        )
    if not review:
        lines.append("| — | — | — |")
    lines.append("")

    missing = [result for result in results if result["status"] == "MISSING"]
    lines += [f"## Только в колоде чтения кандзи ({len(missing)})", ""]
    for result in missing:
        kanji = result["kanji"]
        lines.append(f"- {kanji['front']} — {compact_text(kanji['meaning'], 90)} — `{kanji['note_id']}`")
    if not missing:
        lines.append("- Нет.")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--words-deck", default=DEFAULT_WORDS_DECK)
    parser.add_argument("--kanji-deck", default=DEFAULT_KANJI_DECK)
    parser.add_argument("--words-note-type", default=DEFAULT_WORDS_NOTE_TYPE)
    parser.add_argument("--kanji-note-type", default=DEFAULT_KANJI_NOTE_TYPE)
    kanji_scope = parser.add_mutually_exclusive_group()
    kanji_scope.add_argument(
        "--kanji-tag",
        default=DEFAULT_KANJI_TAG,
        help=(
            "Scan only kanji notes with this tag; a short tag also matches a "
            f"hierarchical suffix. Default: {DEFAULT_KANJI_TAG}"
        ),
    )
    kanji_scope.add_argument(
        "--all-kanji",
        dest="kanji_tag",
        action="store_const",
        const=None,
        help="Ignore the tag filter and scan every present kanji note.",
    )
    parser.add_argument("--backend", choices=["local", "openai"], default=DEFAULT_BACKEND)
    parser.add_argument("--model", help="Embedding model used to build the stored vectors.")
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                        help=f"Semantic candidates per unresolved card. Default: {DEFAULT_TOP}")
    parser.add_argument("--review-threshold", type=float, default=DEFAULT_REVIEW_THRESHOLD,
                        help=f"Cosine threshold for the LLM/manual queue. Default: {DEFAULT_REVIEW_THRESHOLD}")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--review-out", type=Path, default=DEFAULT_REVIEW_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.top <= 0:
        print("error: --top must be positive", file=sys.stderr)
        return 1
    if not -1.0 <= args.review_threshold <= 1.0:
        print("error: --review-threshold must be between -1 and 1", file=sys.stderr)
        return 1
    if args.backend == "local" and args.dimensions is not None:
        print("error: --dimensions is only supported for --backend openai", file=sys.stderr)
        return 1

    model = args.model or (
        DEFAULT_LOCAL_EMBEDDING_MODEL if args.backend == "local" else DEFAULT_OPENAI_EMBEDDING_MODEL
    )
    model_key = embedding_model_key(args.backend, model)
    dim_key = dimension_key(args.dimensions)

    try:
        with connect_read_only(args.db) as connection:
            word_notes = load_indexed_notes(
                connection, args.words_deck, args.words_note_type, model_key, dim_key
            )
            kanji_notes = load_indexed_notes(
                connection,
                args.kanji_deck,
                args.kanji_note_type,
                model_key,
                dim_key,
                required_tag=args.kanji_tag,
            )
        results = scan(kanji_notes, word_notes, args.top, args.review_threshold)
    except (CoverageError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    counts = summary(results)
    output = {
        "schema_version": 1,
        "source": {
            "database": str(args.db),
            "words_deck": args.words_deck,
            "kanji_deck": args.kanji_deck,
            "kanji_tag": args.kanji_tag,
            "embedding_model": model_key,
            "dimension_key": dim_key,
            "review_threshold": args.review_threshold,
        },
        "summary": counts,
        "notes": results,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review(args.review_out, results, counts, args.review_threshold, args.kanji_tag)

    scope = f"tag:{args.kanji_tag}" if args.kanji_tag is not None else "all"
    print(f"words={len(word_notes)} kanji={len(kanji_notes)} scope={scope}")
    print(" ".join(f"{status}={count}" for status, count in counts.items()))
    print(f"json  -> {args.json_out}")
    print(f"review-> {args.review_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
