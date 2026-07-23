#!/usr/bin/env python3
"""Search for exported Anki notes with similar embeddings."""

from __future__ import annotations

import argparse
import heapq
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from embedding_utils import (
    DEFAULT_BACKEND,
    DEFAULT_DB_PATH,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    EmbeddingError,
    LocalEmbeddingModel,
    compact_text,
    connect_database,
    cosine_similarity,
    dimension_key,
    embedding_model_key,
    initialize_embedding_tables,
    request_openai_embeddings,
    require_api_key,
    unpack_vector,
    vector_norm,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find notes with embeddings similar to a note or text query."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--note-id", type=int, help="Note id to use as the query.")
    source.add_argument("--text", help="Free text to embed and use as the query.")
    parser.add_argument(
        "--deck",
        default="Πες το ελληνικά",
        help="Deck to search in. Default: Πες το ελληνικά",
    )
    parser.add_argument(
        "--query-deck",
        help="Deck containing --note-id. Defaults to --deck.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--backend",
        choices=["openai", "local"],
        default=DEFAULT_BACKEND,
        help=f"Embedding backend. Default: {DEFAULT_BACKEND}",
    )
    parser.add_argument(
        "--model",
        help=(
            "Embedding model. Defaults to text-embedding-3-small for OpenAI "
            f"and {DEFAULT_LOCAL_EMBEDDING_MODEL} for local."
        ),
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=None,
        help="Optional embedding dimensions. Use the same value used by build_embeddings.py.",
    )
    parser.add_argument("--top", type=int, default=10, help="Number of matches to show. Default: 10")
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format. Default: text.",
    )
    parser.add_argument(
        "--include-self",
        action="store_true",
        help="Include the query note itself when searching by note id.",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the OpenAI API key. Default: OPENAI_API_KEY",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="OpenAI request timeout in seconds. Default: 60.",
    )
    parser.add_argument(
        "--ca-bundle",
        help=(
            "Optional CA bundle path for TLS verification. "
            "You can also set SSL_CERT_FILE."
        ),
    )
    return parser.parse_args()


def fetch_stored_query_embedding(
    connection: sqlite3.Connection,
    deck: str,
    note_id: int,
    model: str,
    dim_key: str,
) -> tuple[list[float], float] | None:
    row = connection.execute(
        """
        SELECT vector_blob, vector_norm
        FROM note_embeddings
        WHERE deck_name = ?
          AND note_id = ?
          AND embedding_model = ?
          AND dimension_key = ?
        """,
        (deck, note_id, model, dim_key),
    ).fetchone()
    if row is None:
        return None
    vector = unpack_vector(row["vector_blob"])
    return list(vector), float(row["vector_norm"])


def fetch_note_embedding_text(
    connection: sqlite3.Connection,
    deck: str,
    note_id: int,
) -> str:
    row = connection.execute(
        """
        SELECT embedding_text
        FROM anki_notes
        WHERE deck_name = ?
          AND note_id = ?
          AND is_present = 1
        """,
        (deck, note_id),
    ).fetchone()
    if row is None:
        raise EmbeddingError(f"Note {note_id} was not found in deck {deck!r}.")
    return str(row["embedding_text"])


def fetch_note_summary(connection: sqlite3.Connection, deck: str, note_id: int) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT note_id, front_clean, back_clean
        FROM anki_notes
        WHERE deck_name = ?
          AND note_id = ?
          AND is_present = 1
        """,
        (deck, note_id),
    ).fetchone()
    if row is None:
        raise EmbeddingError(f"Note {note_id} was not found in deck {deck!r}.")
    return row


def build_text_query(text: str) -> str:
    if "\n" in text or text.casefold().startswith("greek vocabulary item:"):
        return text
    return f"Greek vocabulary item: {text}"


def embed_query_text(
    text: str,
    backend: str,
    model: str,
    dimensions: int | None,
    api_key_env: str,
    timeout_seconds: float,
    ca_bundle: str | None,
) -> tuple[list[float], float]:
    if backend == "local":
        local_model = LocalEmbeddingModel(model)
        embeddings = local_model.encode([text], batch_size=1)
    else:
        api_key = require_api_key(api_key_env)
        embeddings, _ = request_openai_embeddings(
            [text],
            model,
            api_key,
            dimensions=dimensions,
            timeout_seconds=timeout_seconds,
            ca_bundle=ca_bundle,
        )
    query_vector = embeddings[0]
    return query_vector, vector_norm(query_vector)


def search(
    connection: sqlite3.Connection,
    query_vector: list[float],
    query_norm: float,
    deck: str,
    model: str,
    dim_key: str,
    top: int,
    exclude_note_id: int | None,
    exclude_deck: str | None,
) -> list[tuple[float, int, sqlite3.Row]]:
    rows = connection.execute(
        """
        SELECT
            n.deck_name,
            n.note_id,
            n.front_clean,
            n.back_clean,
            e.vector_blob,
            e.vector_norm
        FROM note_embeddings e
        JOIN anki_notes n
          ON n.deck_name = e.deck_name
         AND n.note_id = e.note_id
        WHERE e.deck_name = ?
          AND e.embedding_model = ?
          AND e.dimension_key = ?
          AND n.is_present = 1
        """,
        (deck, model, dim_key),
    )

    matches: list[tuple[float, int, sqlite3.Row]] = []
    for row in rows:
        if exclude_note_id is not None and row["note_id"] == exclude_note_id and row["deck_name"] == exclude_deck:
            continue
        candidate_vector = unpack_vector(row["vector_blob"])
        score = cosine_similarity(
            query_vector,
            query_norm,
            candidate_vector,
            float(row["vector_norm"]),
        )
        note_id = int(row["note_id"])
        if len(matches) < top:
            heapq.heappush(matches, (score, note_id, row))
        elif score > matches[0][0]:
            heapq.heapreplace(matches, (score, note_id, row))

    return sorted(matches, key=lambda item: item[0], reverse=True)


def build_search_result(
    args: argparse.Namespace,
    model: str,
    model_key: str,
    dim_key: str,
    query_deck: str,
    query_text: str,
    query_note: sqlite3.Row | None,
    matches: list[tuple[float, int, sqlite3.Row]],
) -> dict[str, Any]:
    if query_note is None:
        query: dict[str, Any] = {"type": "text", "text": args.text, "embedding_text": query_text}
    else:
        query = {
            "type": "note",
            "deck": query_deck,
            "note_id": int(query_note["note_id"]),
            "front": str(query_note["front_clean"]),
            "back": str(query_note["back_clean"]),
            "embedding_text": query_text,
        }

    candidates = [
        {
            "rank": index,
            "score": score,
            "deck": str(row["deck_name"]),
            "note_id": int(row["note_id"]),
            "front": str(row["front_clean"]),
            "back": str(row["back_clean"]),
        }
        for index, (score, _note_id, row) in enumerate(matches, start=1)
    ]
    return {
        "search_deck": args.deck,
        "backend": args.backend,
        "model": model,
        "storage_model_key": model_key,
        "dimensions": dim_key,
        "query": query,
        "candidates": candidates,
    }


def markdown_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def print_markdown_result(result: dict[str, Any]) -> None:
    query = result["query"]
    print("# Similar Greek cards")
    print()
    print(f"- Search deck: `{result['search_deck']}`")
    print(f"- Backend: `{result['backend']}`")
    print(f"- Model: `{result['model']}`")
    print()
    print("## Query")
    print()
    if query["type"] == "note":
        print(f"- Note ID: `{query['note_id']}`")
        print(f"- Query deck: `{query['deck']}`")
        print(f"- Front: {markdown_cell(str(query['front']))}")
        print(f"- Back: {markdown_cell(str(query['back']))}")
    else:
        print(f"- Text: {markdown_cell(str(query['text']))}")
    print()
    print("## Candidates")
    print()
    print("| Rank | Score | Note ID | FrontText | BackText |")
    print("| ---: | ---: | ---: | --- | --- |")
    for candidate in result["candidates"]:
        print(
            "| {rank} | {score:.4f} | {note_id} | {front} | {back} |".format(
                rank=candidate["rank"],
                score=candidate["score"],
                note_id=candidate["note_id"],
                front=markdown_cell(str(candidate["front"])),
                back=markdown_cell(str(candidate["back"])),
            )
        )


def print_text_result(result: dict[str, Any]) -> None:
    print(f"Deck: {result['search_deck']}")
    print(f"Backend: {result['backend']}")
    print(f"Model: {result['model']}")
    print(f"Storage model key: {result['storage_model_key']}")
    print(f"Dimensions: {result['dimensions']}")
    print()
    for candidate in result["candidates"]:
        front = compact_text(str(candidate["front"]), 48)
        back = compact_text(str(candidate["back"]), 90)
        print(f"{candidate['rank']:>2}. {candidate['score']:.4f}  {candidate['note_id']}  {front}")
        if back:
            print(f"    {back}")


def main() -> int:
    args = parse_args()
    if args.top <= 0:
        print("error: --top must be positive", file=sys.stderr)
        return 1

    if args.backend == "local" and args.dimensions is not None:
        print("error: --dimensions is only supported for --backend openai", file=sys.stderr)
        return 1

    model = args.model or (
        DEFAULT_LOCAL_EMBEDDING_MODEL
        if args.backend == "local"
        else DEFAULT_OPENAI_EMBEDDING_MODEL
    )
    model_key = embedding_model_key(args.backend, model)
    dim_key = dimension_key(args.dimensions)
    query_deck = args.query_deck or args.deck

    try:
        with connect_database(args.db) as connection:
            initialize_embedding_tables(connection)
            query_note: sqlite3.Row | None = None
            if args.note_id is not None:
                query_note = fetch_note_summary(connection, query_deck, args.note_id)
                query_text = fetch_note_embedding_text(connection, query_deck, args.note_id)
                stored_embedding = fetch_stored_query_embedding(
                    connection,
                    query_deck,
                    args.note_id,
                    model_key,
                    dim_key,
                )
                if stored_embedding is None:
                    query_vector, query_norm = embed_query_text(
                        query_text,
                        args.backend,
                        model,
                        args.dimensions,
                        args.api_key_env,
                        args.timeout,
                        args.ca_bundle,
                    )
                else:
                    query_vector, query_norm = stored_embedding
                exclude_note_id = None if args.include_self else args.note_id
                exclude_deck = None if args.include_self else query_deck
            else:
                query_text = build_text_query(args.text)
                query_vector, query_norm = embed_query_text(
                    query_text,
                    args.backend,
                    model,
                    args.dimensions,
                    args.api_key_env,
                    args.timeout,
                    args.ca_bundle,
                )
                exclude_note_id = None
                exclude_deck = None

            matches = search(
                connection,
                query_vector,
                query_norm,
                args.deck,
                model_key,
                dim_key,
                args.top,
                exclude_note_id,
                exclude_deck,
            )
    except (EmbeddingError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    result = build_search_result(
        args,
        model,
        model_key,
        dim_key,
        query_deck,
        query_text,
        query_note,
        matches,
    )
    if args.output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.output_format == "markdown":
        print_markdown_result(result)
    else:
        print_text_result(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
