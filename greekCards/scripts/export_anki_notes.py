#!/usr/bin/env python3
"""Read Anki notes through AnkiConnect and store cleaned text in SQLite."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ANKI_CONNECT_VERSION = 6
DEFAULT_ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DEFAULT_NOTE_TYPE = "Basic Quizlet Extended"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "greek_cards.sqlite3"
READ_ONLY_ACTIONS = {"version", "deckNames", "findNotes", "notesInfo"}


class AnkiConnectError(RuntimeError):
    pass


class HtmlToTextParser(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "dd",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self._newline()
        elif tag in self.BLOCK_TAGS:
            self._newline()

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS:
            self._newline()

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)

    def _newline(self) -> None:
        if not self.parts or self.parts[-1].endswith("\n"):
            return
        self.parts.append("\n")


def invoke_anki_connect(
    url: str,
    action: str,
    params: dict[str, Any] | None = None,
    timeout_seconds: float = 15.0,
) -> Any:
    if action not in READ_ONLY_ACTIONS:
        raise AnkiConnectError(f"Refusing to call non-read-only AnkiConnect action: {action}")

    payload = json.dumps(
        {
            "action": action,
            "version": ANKI_CONNECT_VERSION,
            "params": params or {},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as error:
        raise AnkiConnectError(
            "Could not reach AnkiConnect. Make sure Anki is running and the "
            "AnkiConnect add-on is installed."
        ) from error

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as error:
        raise AnkiConnectError(f"AnkiConnect returned invalid JSON: {body}") from error

    if parsed.get("error") is not None:
        raise AnkiConnectError(f"AnkiConnect {action} failed: {parsed['error']}")

    return parsed.get("result")


def quote_anki_search_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_find_notes_query(deck: str, note_type: str | None) -> str:
    parts = [f"deck:{quote_anki_search_value(deck)}"]
    if note_type:
        parts.append(f"note:{quote_anki_search_value(note_type)}")
    return " ".join(parts)


def chunked(items: list[int], size: int) -> list[list[int]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def remove_examples_block(raw_text: str) -> str:
    lower = raw_text.lower()
    start = lower.find("[examples]")
    end = lower.find("[/examples]", start + len("[examples]"))
    if start == -1 or end == -1:
        return raw_text
    return raw_text[:start] + raw_text[end + len("[/examples]") :]


def html_to_text(raw_text: str) -> str:
    parser = HtmlToTextParser()
    parser.feed(raw_text)
    parser.close()
    return html.unescape(parser.text())


def clean_text(raw_text: str, remove_examples: bool = False) -> str:
    text = remove_examples_block(raw_text) if remove_examples else raw_text
    text = html_to_text(text)
    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]

    compact_lines: list[str] = []
    previous_blank = True
    for line in lines:
        if not line:
            if not previous_blank:
                compact_lines.append("")
            previous_blank = True
            continue
        compact_lines.append(line)
        previous_blank = False

    while compact_lines and compact_lines[-1] == "":
        compact_lines.pop()

    return "\n".join(compact_lines).strip()


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    )
    return unicodedata.normalize("NFC", without_marks)


def normalize_for_lookup(text: str) -> str:
    text = strip_diacritics(text).casefold()
    text = text.replace("ς", "σ")
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_front_terms(front_clean: str) -> list[str]:
    terms: list[str] = []
    seen_normalized: set[str] = set()
    for term in re.split(r"[\n,/;]+", front_clean):
        term = re.sub(r"\s+", " ", term).strip()
        if not term:
            continue
        normalized = normalize_for_lookup(term)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        terms.append(term)
    return terms


def build_embedding_text(front_clean: str, back_clean: str) -> str:
    parts = []
    if front_clean:
        parts.append(f"Greek vocabulary item: {front_clean}")
    if back_clean:
        meaning = re.sub(r"\s*\n\s*", "; ", back_clean)
        parts.append(f"Meaning: {meaning}")
    return "\n".join(parts)


def stable_content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def field_value(note: dict[str, Any], field_name: str) -> str:
    fields = note.get("fields", {})
    field = fields.get(field_name, {})
    value = field.get("value", "")
    return value if isinstance(value, str) else str(value)


def transform_note(note: dict[str, Any], deck: str, exported_at: str) -> dict[str, Any]:
    front_raw = field_value(note, "FrontText")
    back_raw = field_value(note, "BackText")
    front_clean = clean_text(front_raw)
    back_clean = clean_text(back_raw, remove_examples=True)
    front_terms = extract_front_terms(front_clean)
    embedding_text = build_embedding_text(front_clean, back_clean)
    tags = note.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    payload_for_hash = {
        "model_name": note.get("modelName", ""),
        "tags": sorted(str(tag) for tag in tags),
        "front_raw": front_raw,
        "back_raw": back_raw,
        "front_clean": front_clean,
        "back_clean": back_clean,
        "embedding_text": embedding_text,
    }

    return {
        "note_id": int(note["noteId"]),
        "deck_name": deck,
        "model_name": str(note.get("modelName", "")),
        "tags_json": json.dumps(tags, ensure_ascii=False),
        "front_raw": front_raw,
        "back_raw": back_raw,
        "front_clean": front_clean,
        "back_clean": back_clean,
        "front_normalized": normalize_for_lookup(front_clean),
        "front_terms_json": json.dumps(front_terms, ensure_ascii=False),
        "embedding_text": embedding_text,
        "content_hash": stable_content_hash(payload_for_hash),
        "exported_at": exported_at,
    }


def connect_database(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS anki_notes (
            note_id INTEGER NOT NULL,
            deck_name TEXT NOT NULL,
            model_name TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            front_raw TEXT NOT NULL,
            back_raw TEXT NOT NULL,
            front_clean TEXT NOT NULL,
            back_clean TEXT NOT NULL,
            front_normalized TEXT NOT NULL,
            front_terms_json TEXT NOT NULL,
            embedding_text TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            is_present INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (deck_name, note_id)
        );

        CREATE INDEX IF NOT EXISTS idx_anki_notes_deck_present
            ON anki_notes(deck_name, is_present);

        CREATE INDEX IF NOT EXISTS idx_anki_notes_front_normalized
            ON anki_notes(front_normalized);

        CREATE TABLE IF NOT EXISTS export_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_name TEXT NOT NULL,
            note_type TEXT,
            anki_query TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            total_found INTEGER NOT NULL,
            inserted_count INTEGER NOT NULL,
            updated_count INTEGER NOT NULL,
            unchanged_count INTEGER NOT NULL,
            marked_absent_count INTEGER NOT NULL
        );
        """
    )


def upsert_notes(
    connection: sqlite3.Connection,
    notes: list[dict[str, Any]],
    deck: str,
    note_type: str | None,
    anki_query: str,
    started_at: str,
    finished_at: str,
) -> dict[str, int]:
    existing_query = "SELECT note_id, content_hash FROM anki_notes WHERE deck_name = ?"
    existing_params: list[Any] = [deck]
    if note_type:
        existing_query += " AND model_name = ?"
        existing_params.append(note_type)
    existing_hashes = {
        int(row["note_id"]): str(row["content_hash"])
        for row in connection.execute(existing_query, existing_params)
    }

    inserted = 0
    updated = 0
    unchanged = 0
    current_note_ids = {note["note_id"] for note in notes}

    with connection:
        for note in notes:
            previous_hash = existing_hashes.get(note["note_id"])
            if previous_hash is None:
                inserted += 1
            elif previous_hash != note["content_hash"]:
                updated += 1
            else:
                unchanged += 1

            connection.execute(
                """
                INSERT INTO anki_notes (
                    note_id,
                    deck_name,
                    model_name,
                    tags_json,
                    front_raw,
                    back_raw,
                    front_clean,
                    back_clean,
                    front_normalized,
                    front_terms_json,
                    embedding_text,
                    content_hash,
                    first_seen_at,
                    last_seen_at,
                    is_present
                )
                VALUES (
                    :note_id,
                    :deck_name,
                    :model_name,
                    :tags_json,
                    :front_raw,
                    :back_raw,
                    :front_clean,
                    :back_clean,
                    :front_normalized,
                    :front_terms_json,
                    :embedding_text,
                    :content_hash,
                    :exported_at,
                    :exported_at,
                    1
                )
                ON CONFLICT(deck_name, note_id) DO UPDATE SET
                    model_name = excluded.model_name,
                    tags_json = excluded.tags_json,
                    front_raw = excluded.front_raw,
                    back_raw = excluded.back_raw,
                    front_clean = excluded.front_clean,
                    back_clean = excluded.back_clean,
                    front_normalized = excluded.front_normalized,
                    front_terms_json = excluded.front_terms_json,
                    embedding_text = excluded.embedding_text,
                    content_hash = excluded.content_hash,
                    last_seen_at = excluded.last_seen_at,
                    is_present = 1
                """,
                note,
            )

        absent_scope = "deck_name = ? AND is_present = 1"
        absent_scope_params: list[Any] = [deck]
        if note_type:
            absent_scope += " AND model_name = ?"
            absent_scope_params.append(note_type)

        if current_note_ids:
            placeholders = ", ".join("?" for _ in current_note_ids)
            absent_sql = f"""
                UPDATE anki_notes
                SET is_present = 0, last_seen_at = ?
                WHERE {absent_scope}
                  AND note_id NOT IN ({placeholders})
            """
            absent_params: list[Any] = [
                finished_at,
                *absent_scope_params,
                *sorted(current_note_ids),
            ]
            cursor = connection.execute(absent_sql, absent_params)
        else:
            absent_sql = f"""
                UPDATE anki_notes
                SET is_present = 0, last_seen_at = ?
                WHERE {absent_scope}
            """
            cursor = connection.execute(absent_sql, [finished_at, *absent_scope_params])
        marked_absent = cursor.rowcount

        connection.execute(
            """
            INSERT INTO export_runs (
                deck_name,
                note_type,
                anki_query,
                started_at,
                finished_at,
                total_found,
                inserted_count,
                updated_count,
                unchanged_count,
                marked_absent_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deck,
                note_type,
                anki_query,
                started_at,
                finished_at,
                len(notes),
                inserted,
                updated,
                unchanged,
                marked_absent,
            ),
        )

    return {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "marked_absent": marked_absent,
    }


def fetch_notes(
    url: str,
    deck: str,
    note_type: str | None,
    timeout_seconds: float,
) -> tuple[str, list[dict[str, Any]]]:
    version = invoke_anki_connect(url, "version", timeout_seconds=timeout_seconds)
    if not isinstance(version, int):
        raise AnkiConnectError(f"Unexpected AnkiConnect version response: {version!r}")

    deck_names = invoke_anki_connect(url, "deckNames", timeout_seconds=timeout_seconds)
    if deck not in deck_names:
        available = "\n".join(f"  - {name}" for name in sorted(deck_names))
        raise AnkiConnectError(f"Deck not found: {deck}\nAvailable decks:\n{available}")

    query = build_find_notes_query(deck, note_type)
    note_ids = invoke_anki_connect(
        url,
        "findNotes",
        {"query": query},
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(note_ids, list):
        raise AnkiConnectError(f"Unexpected findNotes response: {note_ids!r}")

    notes: list[dict[str, Any]] = []
    for note_id_chunk in chunked([int(note_id) for note_id in note_ids], 100):
        chunk_notes = invoke_anki_connect(
            url,
            "notesInfo",
            {"notes": note_id_chunk},
            timeout_seconds=timeout_seconds,
        )
        if not isinstance(chunk_notes, list):
            raise AnkiConnectError(f"Unexpected notesInfo response: {chunk_notes!r}")
        notes.extend(chunk_notes)

    return query, notes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export notes from one Anki deck into a local SQLite database. "
            "This script only calls read-only AnkiConnect actions."
        )
    )
    parser.add_argument("--deck", required=True, help="Deck name to export, for example: Πες το ελληνικά")
    parser.add_argument(
        "--note-type",
        default=DEFAULT_NOTE_TYPE,
        help=(
            "Limit export to this Anki note type. "
            f"Default: {DEFAULT_NOTE_TYPE!r}. Use --all-note-types to disable."
        ),
    )
    parser.add_argument(
        "--all-note-types",
        action="store_true",
        help="Export all note types from the selected deck.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--anki-connect-url",
        default=DEFAULT_ANKI_CONNECT_URL,
        help=f"AnkiConnect URL. Default: {DEFAULT_ANKI_CONNECT_URL}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="AnkiConnect request timeout in seconds. Default: 15.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    note_type = None if args.all_note_types else args.note_type
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        anki_query, raw_notes = fetch_notes(
            args.anki_connect_url,
            args.deck,
            note_type,
            args.timeout,
        )
        exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        transformed_notes = [
            transform_note(note, args.deck, exported_at)
            for note in raw_notes
            if isinstance(note, dict)
        ]
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        with connect_database(args.db) as connection:
            initialize_database(connection)
            counts = upsert_notes(
                connection,
                transformed_notes,
                args.deck,
                note_type,
                anki_query,
                started_at,
                finished_at,
            )
    except AnkiConnectError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except sqlite3.Error as error:
        print(f"database error: {error}", file=sys.stderr)
        return 1

    print(f"Deck: {args.deck}")
    print(f"Query: {anki_query}")
    print(f"Database: {args.db}")
    print(f"Found: {len(raw_notes)}")
    print(f"Inserted: {counts['inserted']}")
    print(f"Updated: {counts['updated']}")
    print(f"Unchanged: {counts['unchanged']}")
    print(f"Marked absent: {counts['marked_absent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
