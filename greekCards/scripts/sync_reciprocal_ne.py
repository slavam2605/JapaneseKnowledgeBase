#!/usr/bin/env python3
"""Synchronize missing reciprocal `(не …)` clarifications into the primary deck."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from export_anki_notes import DEFAULT_ANKI_CONNECT_URL, normalize_for_lookup, remove_ne_clarifications


ANKI_CONNECT_VERSION = 6
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "greek_cards.sqlite3"
PRIMARY_DECK = "Πες το ελληνικά"
SOURCE_DECK = "to_process"
REVIEW_TAG = "ai_generated::to_review"
NE_PATTERN = re.compile(r"\(\s*не\b\s*([^)]+)\)", re.IGNORECASE)
NE_SEPARATOR = re.compile(r"\s*,\s*(?:не\s+)?", re.IGNORECASE)
GREEK_TOKEN_PATTERN = re.compile(r"[α-ω]+")
ACCENTED_GREEK_TOKEN_PATTERN = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]+")
GREEK_ARTICLES = frozenset(
    {"ο", "η", "το", "οι", "τα", "τον", "την", "τους", "τις", "του", "της", "των"}
)


class AnkiConnectError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--apply", action="store_true", help="Apply verified reciprocal updates to Anki.")
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
    return f'"{value.replace("\\", "\\\\").replace("\"", "\\\"")}"'


def extract_ne_targets(*texts: str) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in NE_PATTERN.finditer(text):
            for target in NE_SEPARATOR.split(match.group(1)):
                target = target.strip()
                if target and target.casefold() not in seen:
                    targets.append(target)
                    seen.add(target.casefold())
    return targets


def greek_variant(text: str) -> str:
    normalized = normalize_for_lookup(remove_ne_clarifications(text))
    return " ".join(GREEK_TOKEN_PATTERN.findall(normalized))


def accented_greek_variant(text: str) -> str:
    cleaned = remove_ne_clarifications(text).casefold().replace("ς", "σ")
    return " ".join(ACCENTED_GREEK_TOKEN_PATTERN.findall(cleaned))


def without_article(text: str) -> str:
    words = text.split()
    return " ".join(words[1:]) if words and words[0] in GREEK_ARTICLES else text


def variants(text: str) -> set[str]:
    value = greek_variant(text)
    return {variant for variant in {value, without_article(value)} if variant}


def front_terms(row: sqlite3.Row) -> list[str]:
    terms = [str(row["front_clean"])]
    try:
        parsed = json.loads(str(row["front_terms_json"]))
    except json.JSONDecodeError:
        parsed = []
    if isinstance(parsed, list):
        terms.extend(str(term) for term in parsed)
    return terms


def source_label(row: sqlite3.Row) -> str:
    terms = front_terms(row)
    return remove_ne_clarifications(terms[1] if len(terms) > 1 else terms[0])


def load_rows(connection: sqlite3.Connection, deck: str) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT note_id, front_clean, back_clean, front_raw, back_raw, front_terms_json
            FROM anki_notes
            WHERE deck_name = ? AND is_present = 1
            ORDER BY note_id
            """,
            (deck,),
        )
    )


def build_target_indexes(
    rows: list[sqlite3.Row],
) -> tuple[dict[str, set[int]], dict[str, set[int]], dict[str, set[int]]]:
    accented_index: dict[str, set[int]] = defaultdict(set)
    exact_index: dict[str, set[int]] = defaultdict(set)
    loose_index: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        for term in front_terms(row):
            accented = accented_greek_variant(term)
            if accented:
                accented_index[accented].add(int(row["note_id"]))
            exact = greek_variant(term)
            if exact:
                exact_index[exact].add(int(row["note_id"]))
            for variant in variants(term):
                loose_index[variant].add(int(row["note_id"]))
    return accented_index, exact_index, loose_index


def resolve_target_note_ids(
    target: str,
    accented_index: dict[str, set[int]],
    exact_index: dict[str, set[int]],
    loose_index: dict[str, set[int]],
) -> list[int]:
    accented = accented_greek_variant(target)
    if accented and accented_index.get(accented):
        return sorted(accented_index[accented])
    exact = greek_variant(target)
    if exact and exact_index.get(exact):
        return sorted(exact_index[exact])
    return sorted({note_id for variant in variants(target) for note_id in loose_index.get(variant, set())})


def has_marker(back_text: str, label: str) -> bool:
    expected = variants(label)
    return any(expected & variants(target) for target in extract_ne_targets(back_text))


def append_marker(back_raw: str, label: str) -> str:
    marker = f"(не {label})"
    existing_markers = list(NE_PATTERN.finditer(back_raw))
    if existing_markers:
        existing = existing_markers[-1]
        merged = f"(не {existing.group(1).strip()}, {label})"
        return f"{back_raw[:existing.start()]}{merged}{back_raw[existing.end():]}"
    examples = re.search(r"<div[^>]*>\s*\[examples\]\s*</div>", back_raw, flags=re.IGNORECASE)
    if examples:
        return f"{back_raw[:examples.start()]}<br>{marker}{back_raw[examples.start():]}"
    return f"{back_raw}<br>{marker}"


def plan_updates(connection: sqlite3.Connection) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows = load_rows(connection, SOURCE_DECK)
    primary_rows = load_rows(connection, PRIMARY_DECK)
    by_id = {int(row["note_id"]): row for row in primary_rows}
    accented_index, exact_index, loose_index = build_target_indexes(primary_rows)
    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    virtual_back = {note_id: str(row["back_raw"]) for note_id, row in by_id.items()}

    for source in source_rows:
        source_note_id = int(source["note_id"])
        label = source_label(source)
        for target in extract_ne_targets(str(source["front_clean"]), str(source["back_clean"])):
            target_ids = resolve_target_note_ids(target, accented_index, exact_index, loose_index)
            if len(target_ids) != 1:
                skipped.append(
                    {
                        "source_note_id": source_note_id,
                        "source": label,
                        "target": target,
                        "reason": "not found" if not target_ids else f"ambiguous: {target_ids}",
                    }
                )
                continue
            target_note_id = target_ids[0]
            target_row = by_id[target_note_id]
            current_back = virtual_back[target_note_id]
            if has_marker(current_back, label):
                skipped.append(
                    {
                        "source_note_id": source_note_id,
                        "source": label,
                        "target": target,
                        "target_note_id": target_note_id,
                        "reason": "reverse marker already present",
                    }
                )
                continue
            virtual_back[target_note_id] = append_marker(current_back, label)
            planned.append(
                {
                    "source_note_id": source_note_id,
                    "source": label,
                    "target": target,
                    "target_note_id": target_note_id,
                    "target_front": str(target_row["front_clean"]),
                }
            )
    return planned, skipped


def verify_primary_target(note_id: int) -> dict[str, Any]:
    found = invoke("findNotes", {"query": f"deck:{quote_search(PRIMARY_DECK)} nid:{note_id}"})
    if found != [note_id]:
        raise AnkiConnectError(f"Primary note {note_id} could not be verified in {PRIMARY_DECK!r}.")
    notes = invoke("notesInfo", {"notes": [note_id]})
    if len(notes) != 1 or int(notes[0]["noteId"]) != note_id:
        raise AnkiConnectError(f"Primary note {note_id} could not be read back.")
    return notes[0]


def apply_updates(planned: list[dict[str, Any]]) -> tuple[int, list[str]]:
    by_target: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in planned:
        by_target[int(item["target_note_id"])].append(item)

    changed = 0
    errors: list[str] = []
    for target_note_id, items in by_target.items():
        try:
            note = verify_primary_target(target_note_id)
            back_raw = str(note["fields"]["BackText"]["value"])
            changed_back = back_raw
            for item in items:
                if not has_marker(changed_back, str(item["source"])):
                    changed_back = append_marker(changed_back, str(item["source"]))
            if changed_back == back_raw:
                continue
            invoke(
                "updateNoteFields",
                {"note": {"id": target_note_id, "fields": {"BackText": changed_back}}},
            )
            invoke("addTags", {"notes": [target_note_id], "tags": REVIEW_TAG})
            verified = verify_primary_target(target_note_id)
            verified_back = str(verified["fields"]["BackText"]["value"])
            if not all(has_marker(verified_back, str(item["source"])) for item in items):
                raise AnkiConnectError(f"Primary note {target_note_id} did not retain every reverse marker.")
            if REVIEW_TAG not in verified.get("tags", []):
                raise AnkiConnectError(f"Primary note {target_note_id} is missing {REVIEW_TAG}.")
            changed += 1
        except AnkiConnectError as error:
            errors.append(str(error))
    return changed, errors


def markdown_report(planned: list[dict[str, Any]], skipped: list[dict[str, Any]], applied: int | None, errors: list[str]) -> str:
    lines = ["# Reciprocal `(не …)` synchronization", ""]
    if applied is None:
        lines.append("Mode: dry run; Anki was not changed.")
    else:
        lines.append(f"Mode: apply; changed primary notes: {applied}.")
    lines.extend(["", "## Missing reverse markers", "", "| Source note | New marker | Primary note |", "| ---: | --- | --- |"])
    lines.extend(
        f"| {item['source_note_id']} | `{item['source']}` → `(не {item['source']})` | {item['target_note_id']}: `{item['target_front']}` |"
        for item in planned
    )
    lines.extend(["", "## Skipped", "", "| Source note | Target | Reason |", "| ---: | --- | --- |"])
    lines.extend(
        f"| {item['source_note_id']} | `{item['target']}` | {item['reason']} |" for item in skipped
    )
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        with sqlite3.connect(args.db) as connection:
            connection.row_factory = sqlite3.Row
            planned, skipped = plan_updates(connection)
    except sqlite3.Error as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    applied: int | None = None
    errors: list[str] = []
    if args.apply:
        try:
            if invoke("version") is None:
                raise AnkiConnectError("AnkiConnect did not return a version.")
            applied, errors = apply_updates(planned)
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
