#!/usr/bin/env python3
"""Batch dedup scan: for each NEW-deck note, find covering ARCHIVE notes.

Read-only against both the index and Anki: this script only *proposes*
candidate duplicate pairs (JSON + human-readable markdown). Applying decisions
— tagging archive notes `to_remove`, transferring images, tagging new notes
`ai_generated::deduped` — is done by the `dedup-cards` skill after adjudication.

Mechanism (see japaneseCards/tools/EMBEDDINGS.md, use case 2):
  candidates(new) = top-N archive notes by cosine  ∪  all archive notes whose
  normalized reading (`front_normalized`) equals the new note's.
The reading-match union guarantees surface duplicates are never missed just
because their cosine sank below a threshold (e.g. おじいさん / お祖父さん = 0.785).
Cosine only ranks and disambiguates reading-homographs (零(れい) ≠ 例(れい)).

New notes already tagged `ai_generated::deduped` are skipped (idempotent
re-runs); pass --all to rescan everything.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from embedding_utils import (
    DEFAULT_BACKEND,
    DEFAULT_DB_PATH,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    connect_database,
    cosine_similarity,
    dimension_key,
    embedding_model_key,
    initialize_embedding_tables,
    unpack_vector,
)

ARCHIVE_PREFIX = "0. Архив::日本語"
NEW_PREFIX = "新日本語"
DEDUPED_TAG = "ai_generated::deduped"

DEFAULT_JSON_OUT = Path(__file__).resolve().parent.parent / "data" / "removal_candidates.json"
DEFAULT_REVIEW_OUT = Path(__file__).resolve().parent.parent / "data" / "removal_candidates_review.md"

# Tiers, most→least confident that the archive note is a duplicate of the new one.
# Adjudication rule (skill): decide by SURFACE FORM, not meaning.
#   reading_match  = normalized readings (front_normalized) are equal
#   written_match  = the notes share a written form (a term containing a kanji;
#                    for pure-kana words the kana itself is the written form)
# reading+written match ⇒ same word regardless of cosine (translation drift only).
# reading match with DIFFERENT written form ⇒ orthographic variant (high cos) or a
# reading-homograph = different word (low cos, e.g. 例(れい) vs 零(れい)).
TIER_ORDER = ["SURE", "REVIEW", "HOMOPHONE", "SEMANTIC"]
TIER_BLURB = {
    "SURE": "Совпали чтение И письменная форма — почти наверняка один и тот же элемент (косинус вторичен).",
    "REVIEW": "Чтение совпало, форма записи разная, косинус ≥0.80 — вероятно орфографический вариант (20歳/二十歳, 子供/子ども).",
    "HOMOPHONE": "Чтение совпало, форма разная, косинус <0.80 — скорее РАЗНЫЕ слова-омографы (例/零, 着る/切る) — проверить.",
    "SEMANTIC": "Высокий косинус, но РАЗНОЕ чтение — обычно НЕ дубль (小さな vs 小さい, 朝食/朝ごはん).",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH,
                        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}")
    parser.add_argument("--archive-prefix", default=ARCHIVE_PREFIX,
                        help=f"Deck prefix of the archive. Default: {ARCHIVE_PREFIX!r}")
    parser.add_argument("--new-prefix", default=NEW_PREFIX,
                        help=f"Deck prefix of the new decks. Default: {NEW_PREFIX!r}")
    parser.add_argument("--top", type=int, default=8,
                        help="Top-N archive neighbours by cosine per new note. Default: 8")
    parser.add_argument("--all", action="store_true",
                        help=f"Rescan every new note, including those already tagged {DEDUPED_TAG!r}.")
    parser.add_argument("--backend", choices=["openai", "local"], default=DEFAULT_BACKEND)
    parser.add_argument("--model", help="Embedding model (must match build_embeddings.py).")
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--review-out", type=Path, default=DEFAULT_REVIEW_OUT)
    return parser.parse_args()


def escape_like_prefix(prefix: str) -> str:
    return prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def load_notes(
    connection: sqlite3.Connection,
    deck_prefix: str,
    model_key: str,
    dim_key: str,
) -> list[dict]:
    """Load present notes under a deck prefix together with their embedding vectors."""
    rows = connection.execute(
        """
        SELECT
            n.note_id, n.deck_name, n.front_clean, n.back_clean,
            n.front_normalized, n.front_terms_json, n.tags_json,
            e.vector_blob, e.vector_norm
        FROM note_embeddings e
        JOIN anki_notes n
          ON n.deck_name = e.deck_name AND n.note_id = e.note_id
        WHERE n.deck_name LIKE ? ESCAPE '\\'
          AND e.embedding_model = ?
          AND e.dimension_key = ?
          AND n.is_present = 1
        """,
        (escape_like_prefix(deck_prefix) + "%", model_key, dim_key),
    )
    notes: list[dict] = []
    for row in rows:
        notes.append({
            "note_id": int(row["note_id"]),
            "deck_name": str(row["deck_name"]),
            "front_clean": str(row["front_clean"]),
            "back_clean": str(row["back_clean"]),
            "front_normalized": str(row["front_normalized"]),
            "terms": set(json.loads(row["front_terms_json"] or "[]")),
            "tags": list(json.loads(row["tags_json"] or "[]")),
            "vector": unpack_vector(row["vector_blob"]),
            "norm": float(row["vector_norm"]),
        })
    return notes


def has_han(text: str) -> bool:
    return any("一" <= c <= "鿿" or "㐀" <= c <= "䶿" for c in text)


def written_forms(terms: set[str]) -> set[str]:
    """Kanji-bearing surface forms; for a pure-kana word its kana is the form."""
    kanji = {t for t in terms if has_han(t)}
    return kanji if kanji else set(terms)


def classify(cos: float, reading_match: bool, written_match: bool) -> str:
    if reading_match and written_match:
        return "SURE"
    if reading_match and cos >= 0.80:
        return "REVIEW"
    if reading_match:
        return "HOMOPHONE"
    if cos >= 0.90:
        return "SEMANTIC"
    return "IGNORE"


def scan(new_notes: list[dict], archive: list[dict], top: int) -> tuple[list[dict], list[dict]]:
    """Return (candidate pairs, new notes with no candidate)."""
    by_reading: dict[str, list[dict]] = {}
    for a in archive:
        key = a["front_normalized"]
        if key:
            by_reading.setdefault(key, []).append(a)

    pairs: list[dict] = []
    no_candidate: list[dict] = []
    for nn in new_notes:
        scored = [
            (cosine_similarity(nn["vector"], nn["norm"], a["vector"], a["norm"]), a)
            for a in archive
        ]
        scored.sort(key=lambda item: item[0], reverse=True)

        # top-N by cosine ∪ every reading-match, regardless of cosine rank
        selected: dict[int, tuple[float, dict]] = {}
        for cos, a in scored[:top]:
            selected[a["note_id"]] = (cos, a)
        cos_by_arch = {a["note_id"]: cos for cos, a in scored}
        for a in by_reading.get(nn["front_normalized"], []):
            selected.setdefault(a["note_id"], (cos_by_arch.get(a["note_id"], 0.0), a))

        new_written = written_forms(nn["terms"])
        note_pairs: list[dict] = []
        for cos, a in selected.values():
            reading_match = bool(nn["front_normalized"]) and nn["front_normalized"] == a["front_normalized"]
            written_match = bool(new_written & written_forms(a["terms"]))
            tier = classify(cos, reading_match, written_match)
            if tier == "IGNORE":
                continue
            note_pairs.append({
                "new_id": nn["note_id"],
                "new_deck": nn["deck_name"],
                "new_front": nn["front_clean"],
                "arch_id": a["note_id"],
                "arch_deck": a["deck_name"].split("::")[-1],
                "arch_front": a["front_clean"],
                "arch_meaning": a["back_clean"].splitlines()[0] if a["back_clean"] else "",
                "cos": round(cos, 4),
                "reading_match": reading_match,
                "written_match": written_match,
                "tier": tier,
            })
        if note_pairs:
            note_pairs.sort(key=lambda p: (TIER_ORDER.index(p["tier"]), -p["cos"]))
            pairs.extend(note_pairs)
        else:
            no_candidate.append({"new_id": nn["note_id"], "new_deck": nn["deck_name"], "new_front": nn["front_clean"]})
    return pairs, no_candidate


def write_review(path: Path, pairs: list[dict], no_candidate: list[dict], skipped: int) -> None:
    lines = [
        "# Кандидаты на удаление — ручной просмотр",
        "",
        "Сгенерировано `tools/dedup_scan.py` (read-only). **Решать по ПОВЕРХНОСТНОЙ ФОРМЕ** "
        "(чтение + кандзи), не по близости смысла. Подтверждённые дубли обрабатывает скилл "
        "`dedup-cards`: переносит картинку в новую карту, вешает `to_remove` на старую, "
        f"`ai_generated::deduped` на новую. Пропущено уже продедупленных новых заметок: {skipped}.",
        "",
    ]
    for tier in TIER_ORDER:
        tier_pairs = [p for p in pairs if p["tier"] == tier]
        if not tier_pairs:
            continue
        lines += [f"## {tier} ({len(tier_pairs)})", "", f"> {TIER_BLURB[tier]}", "",
                  "| cos | архив | значение | подколода | покрывает (новая) | new_id | arch_id |",
                  "|---|---|---|---|---|---|---|"]
        for p in tier_pairs:
            lines.append(
                f"| {p['cos']:.4f} | {p['arch_front']} | {p['arch_meaning']} | {p['arch_deck']} "
                f"| {p['new_front']} | {p['new_id']} | {p['arch_id']} |"
            )
        lines.append("")
    lines += [f"## Новые заметки без кандидатов ({len(no_candidate)})", "",
              "> Проверены, дублей в архиве нет. Скилл всё равно ставит `ai_generated::deduped`.", ""]
    for nc in no_candidate:
        lines.append(f"- {nc['new_front']} — `{nc['new_id']}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    model = args.model or (
        DEFAULT_LOCAL_EMBEDDING_MODEL if args.backend == "local" else DEFAULT_OPENAI_EMBEDDING_MODEL
    )
    model_key = embedding_model_key(args.backend, model)
    dim_key = dimension_key(args.dimensions)

    with connect_database(args.db) as connection:
        initialize_embedding_tables(connection)
        archive = load_notes(connection, args.archive_prefix, model_key, dim_key)
        new_notes = load_notes(connection, args.new_prefix, model_key, dim_key)

    total_new = len(new_notes)
    if not args.all:
        new_notes = [n for n in new_notes if DEDUPED_TAG not in n["tags"]]
    skipped = total_new - len(new_notes)

    if not archive:
        print(f"error: no archive notes under prefix {args.archive_prefix!r} — build the index first "
              f"(see tools/EMBEDDINGS.md).")
        return 1

    pairs, no_candidate = scan(new_notes, archive, args.top)

    args.json_out.write_text(json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8")
    write_review(args.review_out, pairs, no_candidate, skipped)

    by_tier = {t: sum(1 for p in pairs if p["tier"] == t) for t in TIER_ORDER}
    print(f"archive={len(archive)} new_scanned={len(new_notes)} skipped_deduped={skipped}")
    print(f"pairs={len(pairs)} " + " ".join(f"{t}={by_tier[t]}" for t in TIER_ORDER))
    print(f"new_without_candidate={len(no_candidate)}")
    print(f"json  -> {args.json_out}")
    print(f"review-> {args.review_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
