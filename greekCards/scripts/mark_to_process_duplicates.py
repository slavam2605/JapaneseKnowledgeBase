#!/usr/bin/env python3
"""Mark exact lexical duplicates in `to_process` without deleting them."""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from embedding_utils import cosine_similarity, unpack_vector, vector_norm
from export_anki_notes import DEFAULT_ANKI_CONNECT_URL, normalize_for_lookup, remove_ne_clarifications


ANKI_CONNECT_VERSION = 6
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "greek_cards.sqlite3"
PRIMARY_DECK = "Πες το ελληνικά"
SOURCE_DECK = "to_process"
REMOVE_TAG = "to_remove"
MODEL_KEY = "local:BAAI/bge-m3"
DIMENSION_KEY = "default"
GREEK_TOKEN_PATTERN = re.compile(r"[α-ω]+")
GREEK_ARTICLES = frozenset(
    {"ο", "η", "το", "οι", "τα", "τον", "την", "τους", "τις", "του", "της", "των"}
)


class AnkiConnectError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--apply", action="store_true", help="Apply confirmed duplicate markings to Anki.")
    parser.add_argument(
        "--confirm-note-id",
        type=int,
        action="append",
        default=[],
        help="A to_process note id confirmed as a duplicate after semantic review. Repeat as needed.",
    )
    parser.add_argument("--report", type=Path, help="Write the plan and outcome as Markdown.")
    return parser.parse_args()


def invoke(action: str, params: dict[str, Any] | None = None) -> Any:
    payload = json.dumps(
        {"action": action, "version": ANKI_CONNECT_VERSION, "params": params or {}}, ensure_ascii=False
    ).encode("utf-8")
    request = urllib.request.Request(
        DEFAULT_ANKI_CONNECT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30.0) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise AnkiConnectError("Could not reach AnkiConnect.") from error
    if parsed.get("error") is not None:
        raise AnkiConnectError(f"AnkiConnect {action} failed: {parsed['error']}")
    return parsed.get("result")


def quote_search(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def canonical_term(text: str) -> str:
    normalized = normalize_for_lookup(remove_ne_clarifications(text))
    greek = " ".join(GREEK_TOKEN_PATTERN.findall(normalized))
    words = greek.split()
    if words and words[0] in GREEK_ARTICLES:
        words = words[1:]
    return " ".join(words)


def front_terms(row: sqlite3.Row) -> list[str]:
    terms = [str(row["front_clean"])]
    try:
        parsed = json.loads(str(row["front_terms_json"]))
    except json.JSONDecodeError:
        parsed = []
    if isinstance(parsed, list):
        terms.extend(str(term) for term in parsed)
    return terms


def canonical_terms(row: sqlite3.Row) -> set[str]:
    return {term for value in front_terms(row) if (term := canonical_term(value)) and len(term) > 1}


def load_rows(connection: sqlite3.Connection, deck: str) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT n.note_id, n.front_clean, n.back_clean, n.back_raw, n.front_terms_json, n.tags_json,
                   e.vector_blob, e.vector_norm
            FROM anki_notes n
            LEFT JOIN note_embeddings e
              ON e.deck_name = n.deck_name
             AND e.note_id = n.note_id
             AND e.embedding_model = ?
             AND e.dimension_key = ?
             AND e.source_content_hash = n.content_hash
            WHERE n.deck_name = ? AND n.is_present = 1
            ORDER BY n.note_id
            """,
            (MODEL_KEY, DIMENSION_KEY, deck),
        )
    )


def similarity(source: sqlite3.Row, primary: sqlite3.Row) -> float | None:
    if source["vector_blob"] is None or primary["vector_blob"] is None:
        return None
    left = unpack_vector(source["vector_blob"])
    right = unpack_vector(primary["vector_blob"])
    left_norm = float(source["vector_norm"] or vector_norm(left))
    right_norm = float(primary["vector_norm"] or vector_norm(right))
    return cosine_similarity(left, left_norm, right, right_norm)


def plan_duplicates(connection: sqlite3.Connection) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary_rows = load_rows(connection, PRIMARY_DECK)
    source_rows = load_rows(connection, SOURCE_DECK)
    primary_by_id = {int(row["note_id"]): row for row in primary_rows}
    index: dict[str, set[int]] = defaultdict(set)
    primary_terms: dict[int, set[str]] = {}
    for row in primary_rows:
        note_id = int(row["note_id"])
        terms = canonical_terms(row)
        primary_terms[note_id] = terms
        for term in terms:
            index[term].add(note_id)

    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source in source_rows:
        source_id = int(source["note_id"])
        source_terms = canonical_terms(source)
        candidate_ids = {note_id for term in source_terms for note_id in index.get(term, set())}
        if not candidate_ids:
            continue

        source_whole = canonical_term(str(source["front_clean"]))
        priorities: dict[int, int] = {}
        for note_id in candidate_ids:
            primary_whole = canonical_term(str(primary_by_id[note_id]["front_clean"]))
            priorities[note_id] = 2 if source_whole and source_whole == primary_whole else 1
        best_priority = max(priorities.values())
        best_ids = sorted(note_id for note_id, priority in priorities.items() if priority == best_priority)
        if len(best_ids) != 1:
            skipped.append(
                {
                    "source_note_id": source_id,
                    "source_front": str(source["front_clean"]),
                    "reason": f"ambiguous exact matches: {best_ids}",
                }
            )
            continue

        primary = primary_by_id[best_ids[0]]
        prefix = f"(дубликат {primary['front_clean']})"
        tags = json.loads(str(source["tags_json"]))
        back_raw = str(source["back_raw"])
        has_prefix = back_raw.lstrip().startswith(prefix)
        has_other_duplicate_prefix = back_raw.lstrip().startswith("(дубликат ") and not has_prefix
        if has_other_duplicate_prefix:
            skipped.append(
                {
                    "source_note_id": source_id,
                    "source_front": str(source["front_clean"]),
                    "reason": "a different duplicate marker is already present",
                }
            )
            continue
        if has_prefix and REMOVE_TAG in tags:
            continue
        planned.append(
            {
                "source_note_id": source_id,
                "source_front": str(source["front_clean"]),
                "primary_note_id": int(primary["note_id"]),
                "primary_front": str(primary["front_clean"]),
                "prefix": prefix,
                "needs_back": not has_prefix,
                "needs_tag": REMOVE_TAG not in tags,
                "embedding_score": similarity(source, primary),
            }
        )
    return planned, skipped


def verify_note(note_id: int, deck: str) -> dict[str, Any]:
    found = invoke("findNotes", {"query": f"deck:{quote_search(deck)} nid:{note_id}"})
    if found != [note_id]:
        raise AnkiConnectError(f"Note {note_id} could not be verified in {deck!r}.")
    notes = invoke("notesInfo", {"notes": [note_id]})
    if len(notes) != 1 or int(notes[0]["noteId"]) != note_id:
        raise AnkiConnectError(f"Note {note_id} could not be read back.")
    return notes[0]


def apply_duplicates(planned: list[dict[str, Any]]) -> tuple[int, list[str]]:
    changed = 0
    errors: list[str] = []
    for item in planned:
        source_id = int(item["source_note_id"])
        try:
            verify_note(int(item["primary_note_id"]), PRIMARY_DECK)
            note = verify_note(source_id, SOURCE_DECK)
            back_raw = str(note["fields"]["BackText"]["value"])
            prefix = str(item["prefix"])
            if back_raw.lstrip().startswith("(дубликат ") and not back_raw.lstrip().startswith(prefix):
                raise AnkiConnectError(f"Note {source_id} has a different duplicate marker.")
            if not back_raw.lstrip().startswith(prefix):
                updated_back = f"{prefix}<br>{back_raw}" if back_raw else prefix
                invoke("updateNoteFields", {"note": {"id": source_id, "fields": {"BackText": updated_back}}})
            if REMOVE_TAG not in note.get("tags", []):
                invoke("addTags", {"notes": [source_id], "tags": REMOVE_TAG})
            verified = verify_note(source_id, SOURCE_DECK)
            verified_back = str(verified["fields"]["BackText"]["value"])
            if not verified_back.lstrip().startswith(prefix) or REMOVE_TAG not in verified.get("tags", []):
                raise AnkiConnectError(f"Duplicate marking did not persist for note {source_id}.")
            changed += 1
        except AnkiConnectError as error:
            errors.append(str(error))
    return changed, errors


def markdown_report(planned: list[dict[str, Any]], skipped: list[dict[str, Any]], applied: int | None, errors: list[str]) -> str:
    lines = ["# Duplicate detection for `to_process`", ""]
    lines.append("Mode: dry run; Anki was not changed." if applied is None else f"Mode: apply; marked notes: {applied}.")
    lines.extend(["", "## Lexical candidates", "", "| to_process | Primary card | Embedding score |", "| ---: | --- | ---: |"])
    for item in planned:
        score = "—" if item["embedding_score"] is None else f"{item['embedding_score']:.4f}"
        lines.append(
            f"| {item['source_note_id']}: `{item['source_front']}` | {item['primary_note_id']}: `{item['primary_front']}` | {score} |"
        )
    lines.extend(["", "## Skipped", "", "| to_process | Reason |", "| ---: | --- |"])
    lines.extend(f"| {item['source_note_id']}: `{item['source_front']}` | {item['reason']} |" for item in skipped)
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        with sqlite3.connect(args.db) as connection:
            connection.row_factory = sqlite3.Row
            planned, skipped = plan_duplicates(connection)
    except sqlite3.Error as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    applied: int | None = None
    errors: list[str] = []
    if args.apply:
        confirmed_ids = set(args.confirm_note_id)
        selected = [item for item in planned if int(item["source_note_id"]) in confirmed_ids]
        unknown_ids = confirmed_ids - {int(item["source_note_id"]) for item in planned}
        if unknown_ids:
            errors.append(f"Confirmed ids are not current lexical candidates: {sorted(unknown_ids)}")
        if not selected:
            errors.append("No lexical candidates were explicitly confirmed for application.")
        try:
            if invoke("version") is None:
                raise AnkiConnectError("AnkiConnect did not return a version.")
            applied, apply_errors = apply_duplicates(selected)
            errors.extend(apply_errors)
        except AnkiConnectError as error:
            errors.append(str(error))
            applied = 0

    report = markdown_report(planned, skipped, applied, errors)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
        print(f"Report: {args.report}")
    else:
        print(report, end="")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
