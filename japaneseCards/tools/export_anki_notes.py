#!/usr/bin/env python3
"""Read Japanese Anki notes through AnkiConnect and store cleaned text in SQLite.

Adapted from the greekCards exporter. The storage schema is intentionally
identical (front_clean / back_clean / front_normalized / front_terms_json /
embedding_text) so build_embeddings.py and search_similar.py are reused as-is.
The Japanese-specific parts are: per-note-type field extraction, furigana/ruby
stripping, and kana-based normalization for later deduplication.
"""

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
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "anki_index.sqlite3"
READ_ONLY_ACTIONS = {"version", "deckNames", "findNotes", "notesInfo"}


class AnkiConnectError(RuntimeError):
    pass


class HtmlToTextParser(HTMLParser):
    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "dd", "div", "dl", "dt",
        "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
        "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
        "section", "table", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" or tag in self.BLOCK_TAGS:
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
        {"action": action, "version": ANKI_CONNECT_VERSION, "params": params or {}}
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
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


def html_to_text(raw_text: str) -> str:
    parser = HtmlToTextParser()
    parser.feed(raw_text)
    parser.close()
    return html.unescape(parser.text())


def clean_text(raw_text: str) -> str:
    """Strip HTML, [sound:...] tags, and collapse whitespace into tidy lines."""
    text = html_to_text(raw_text)
    text = re.sub(r"\[sound:[^\]]+\]", " ", text)
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


# Ruby / furigana notation used across the archive decks: 漢字(かんじ), 漢字（かんじ）,
# 漢字[かんじ]. Keep the base kanji, drop the parenthesised reading, for cleaner text.
RUBY_PATTERN = re.compile(r"([一-鿿々〆ヵヶ]+)[\(（\[]([぀-ヿ・ー]+)[\)）\]]")


def strip_ruby(text: str) -> str:
    return RUBY_PATTERN.sub(r"\1", text)


def normalize_reading(text: str) -> str:
    """Normalize a Japanese surface/reading for exact-match dedup.

    NFKC-fold, drop everything except kana/kanji, and collapse. Katakana is
    folded to hiragana so コーヒー and こーひー compare equal on the reading axis.
    """
    text = unicodedata.normalize("NFKC", text)
    folded = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:  # katakana -> hiragana
            ch = chr(code - 0x60)
        folded.append(ch)
    text = "".join(folded)
    text = re.sub(r"[^぀-ゟ一-鿿々〆ー]", "", text)
    return text.strip()


# Per-note-type field mapping. Values are Anki field names.
#   kanji    -> kanji surface (may be empty; then kana is the headword)
#   kana     -> reading in kana
#   headword -> explicit headword override (grammar patterns)
#   meaning  -> primary translation / definition
#   examples -> example sentences
#   extra    -> additional context folded into the embedding text
MODEL_FIELD_MAP: dict[str, dict[str, Any]] = {
    # --- Archive (0. Архив::日本語) ---
    "MNN: words": {
        "kana": "furigana", "kanji": "kanji", "meaning": "translation",
        "examples": "examples", "extra": ["notes", "grammar_info"],
    },
    "Words (JP->RU side only)": {
        "kana": "furigana", "kanji": "kanji", "meaning": "translation",
        "examples": "examples", "extra": ["notes", "grammar_info"],
    },
    "KanjiWordsReading": {
        "kanji": "Kanji word", "kana": "Reading", "meaning": "Translation",
    },
    "Kanji Card-e4d3f": {
        "kanji": "Kanji", "meaning": "Main translation",
        "extra": ["On readings", "Kun readings", "Words", "Notes"],
    },
    "Grammar card": {
        "headword": "Grammar form", "meaning": "Explanation",
        "examples": "Sentence", "extra": ["Translation", "Comments"],
    },
    # --- New decks (新日本語::*) ---
    "AiGeneratedJapaneseWords": {
        "kana": "Kana", "kanji": "Kanji", "meaning": "Definition",
        "examples": "Examples", "extra": ["Word", "NoteRU"],
    },
    "AiGeneratedJapaneseKanji": {
        "kanji": "Kanji", "kana": "Kana", "meaning": "Meaning", "extra": ["Hint"],
    },
    "AiGeneratedJapaneseGrammar": {
        "headword": "Grammar", "meaning": "Meaning",
        "examples": "Expressions", "extra": ["Notes", "Hint"],
    },
}


def field_value(note: dict[str, Any], field_name: str) -> str:
    field = note.get("fields", {}).get(field_name, {})
    value = field.get("value", "")
    return value if isinstance(value, str) else str(value)


def extract_semantics(note: dict[str, Any]) -> dict[str, str]:
    """Map a note of any known type into common (kanji, kana, meaning, examples, extra)."""
    model = str(note.get("modelName", ""))
    spec = MODEL_FIELD_MAP.get(model)

    if spec is None:
        # Unknown type: fold every non-empty field into the meaning text.
        parts = [clean_text(field_value(note, name)) for name in note.get("fields", {})]
        joined = " / ".join(p for p in parts if p)
        return {"kanji": "", "kana": "", "headword": "", "meaning": joined, "examples": "", "extra": ""}

    kanji = clean_text(field_value(note, spec["kanji"])) if "kanji" in spec else ""
    # Old archive decks were built by a script that writes the literal placeholder
    # "kana" into the kanji field for kana-only words. Treat it as "no kanji" so the
    # reading becomes the headword (e.g. しかる, not "kana（しかる）").
    if kanji.lower() == "kana":
        kanji = ""
    kana = clean_text(field_value(note, spec["kana"])) if "kana" in spec else ""
    headword = clean_text(field_value(note, spec["headword"])) if "headword" in spec else ""
    meaning = clean_text(field_value(note, spec["meaning"])) if "meaning" in spec else ""
    examples = strip_ruby(clean_text(field_value(note, spec["examples"]))) if "examples" in spec else ""
    extra_parts = [strip_ruby(clean_text(field_value(note, name))) for name in spec.get("extra", [])]
    extra = "\n".join(p for p in extra_parts if p)
    return {
        "kanji": kanji, "kana": kana, "headword": headword,
        "meaning": meaning, "examples": examples, "extra": extra,
    }


def build_embedding_text(sem: dict[str, str]) -> str:
    """Lean text for embedding: ``headword（reading） meaning``.

    Deliberately drops examples and the extra/labels. A/B tested against a
    labelled form (意味:/例: + extra): this lean form gives markedly higher
    true-duplicate cosine (0.88 -> 0.95), more true dups ranked #1 (81% -> 88%),
    a wider top1-top2 margin (0.08 -> 0.15, so thresholding is more reliable),
    and pushes homophones apart (零(れい) vs 例(れい): 0.60 -> 0.40). The space
    before the meaning is for readability only; the model is insensitive to it.
    The richer text (readings, examples) still lives in back_clean for display.
    """
    head = sem["headword"] or sem["kanji"] or sem["kana"]
    reading = f"（{sem['kana']}）" if sem["kana"] and sem["kana"] != head else ""
    meaning = re.sub(r"\s*\n\s*", "; ", sem["meaning"])
    return f"{head}{reading} {meaning}".strip()


def stable_content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def transform_note(note: dict[str, Any], deck: str, exported_at: str) -> dict[str, Any]:
    sem = extract_semantics(note)
    head = sem["headword"] or sem["kanji"] or sem["kana"]

    reading_suffix = f"（{sem['kana']}）" if sem["kana"] and sem["kana"] != head else ""
    front_clean = f"{head}{reading_suffix}".strip()

    back_parts = [sem["meaning"]]
    if sem["extra"]:
        back_parts.append(sem["extra"])
    back_clean = "\n".join(p for p in back_parts if p).strip()

    embedding_text = build_embedding_text(sem)

    # Normalized reading key for later dedup: prefer kana, fall back to headword.
    front_normalized = normalize_reading(sem["kana"] or head)
    terms = [t for t in (sem["kanji"], sem["kana"], sem["headword"]) if t]
    seen: set[str] = set()
    front_terms = [t for t in terms if not (t in seen or seen.add(t))]

    tags = note.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    payload_for_hash = {
        "model_name": note.get("modelName", ""),
        "tags": sorted(str(tag) for tag in tags),
        "front_clean": front_clean,
        "back_clean": back_clean,
        "embedding_text": embedding_text,
    }

    return {
        "note_id": int(note["noteId"]),
        "deck_name": deck,
        "model_name": str(note.get("modelName", "")),
        "tags_json": json.dumps(tags, ensure_ascii=False),
        "front_raw": front_clean,
        "back_raw": back_clean,
        "front_clean": front_clean,
        "back_clean": back_clean,
        "front_normalized": front_normalized,
        "front_terms_json": json.dumps(front_terms, ensure_ascii=False),
        "embedding_text": embedding_text,
        # content_hash tracks any field change (incl. tags) for the export's own
        # inserted/updated bookkeeping. embedding_hash depends ONLY on embedding_text
        # so build_embeddings re-embeds solely when the embedded text changes — tag
        # churn (to_remove, ai_generated::to_review, ...) no longer forces recompute.
        "content_hash": stable_content_hash(payload_for_hash),
        "embedding_hash": stable_content_hash({"embedding_text": embedding_text}),
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
            embedding_hash TEXT NOT NULL DEFAULT '',
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
    # Migration for databases created before embedding_hash existed.
    columns = {row[1] for row in connection.execute("PRAGMA table_info(anki_notes)")}
    if "embedding_hash" not in columns:
        connection.execute("ALTER TABLE anki_notes ADD COLUMN embedding_hash TEXT NOT NULL DEFAULT ''")


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

    inserted = updated = unchanged = 0
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
                    note_id, deck_name, model_name, tags_json, front_raw, back_raw,
                    front_clean, back_clean, front_normalized, front_terms_json,
                    embedding_text, content_hash, embedding_hash,
                    first_seen_at, last_seen_at, is_present
                )
                VALUES (
                    :note_id, :deck_name, :model_name, :tags_json, :front_raw, :back_raw,
                    :front_clean, :back_clean, :front_normalized, :front_terms_json,
                    :embedding_text, :content_hash, :embedding_hash,
                    :exported_at, :exported_at, 1
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
                    embedding_hash = excluded.embedding_hash,
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
            cursor = connection.execute(
                f"UPDATE anki_notes SET is_present = 0, last_seen_at = ? "
                f"WHERE {absent_scope} AND note_id NOT IN ({placeholders})",
                [finished_at, *absent_scope_params, *sorted(current_note_ids)],
            )
        else:
            cursor = connection.execute(
                f"UPDATE anki_notes SET is_present = 0, last_seen_at = ? WHERE {absent_scope}",
                [finished_at, *absent_scope_params],
            )
        marked_absent = cursor.rowcount

        connection.execute(
            """
            INSERT INTO export_runs (
                deck_name, note_type, anki_query, started_at, finished_at,
                total_found, inserted_count, updated_count, unchanged_count, marked_absent_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (deck, note_type, anki_query, started_at, finished_at,
             len(notes), inserted, updated, unchanged, marked_absent),
        )

    return {"inserted": inserted, "updated": updated, "unchanged": unchanged, "marked_absent": marked_absent}


def fetch_notes(
    url: str, deck: str, note_type: str | None, timeout_seconds: float
) -> tuple[str, list[dict[str, Any]]]:
    version = invoke_anki_connect(url, "version", timeout_seconds=timeout_seconds)
    if not isinstance(version, int):
        raise AnkiConnectError(f"Unexpected AnkiConnect version response: {version!r}")

    deck_names = invoke_anki_connect(url, "deckNames", timeout_seconds=timeout_seconds)
    if deck not in deck_names:
        available = "\n".join(f"  - {name}" for name in sorted(deck_names))
        raise AnkiConnectError(f"Deck not found: {deck}\nAvailable decks:\n{available}")

    query = build_find_notes_query(deck, note_type)
    note_ids = invoke_anki_connect(url, "findNotes", {"query": query}, timeout_seconds=timeout_seconds)
    if not isinstance(note_ids, list):
        raise AnkiConnectError(f"Unexpected findNotes response: {note_ids!r}")

    notes: list[dict[str, Any]] = []
    for note_id_chunk in chunked([int(note_id) for note_id in note_ids], 100):
        chunk_notes = invoke_anki_connect(
            url, "notesInfo", {"notes": note_id_chunk}, timeout_seconds=timeout_seconds
        )
        if not isinstance(chunk_notes, list):
            raise AnkiConnectError(f"Unexpected notesInfo response: {chunk_notes!r}")
        notes.extend(chunk_notes)
    return query, notes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export notes from one Anki deck into a local SQLite database. "
            "Handles the archive and new Japanese note types. Read-only AnkiConnect."
        )
    )
    parser.add_argument("--deck", required=True, help="Deck name to export (exact, includes subdeck path).")
    parser.add_argument("--note-type", default=None, help="Optional: limit to this note type. Default: all.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help=f"SQLite path. Default: {DEFAULT_DB_PATH}")
    parser.add_argument("--anki-connect-url", default=DEFAULT_ANKI_CONNECT_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        anki_query, raw_notes = fetch_notes(args.anki_connect_url, args.deck, args.note_type, args.timeout)
        exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        transformed = [transform_note(n, args.deck, exported_at) for n in raw_notes if isinstance(n, dict)]
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with connect_database(args.db) as connection:
            initialize_database(connection)
            counts = upsert_notes(connection, transformed, args.deck, args.note_type,
                                  anki_query, started_at, finished_at)
    except AnkiConnectError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except sqlite3.Error as error:
        print(f"database error: {error}", file=sys.stderr)
        return 1

    print(f"Deck: {args.deck}")
    print(f"Query: {anki_query}")
    print(f"Database: {args.db}")
    print(f"Found: {len(raw_notes)}  Inserted: {counts['inserted']}  "
          f"Updated: {counts['updated']}  Unchanged: {counts['unchanged']}  "
          f"Marked absent: {counts['marked_absent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
