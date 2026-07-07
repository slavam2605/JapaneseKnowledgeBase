#!/usr/bin/env python3
"""Build embeddings for exported Anki notes."""

from __future__ import annotations

import argparse
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
    connect_database,
    dimension_key,
    embedding_model_key,
    initialize_embedding_tables,
    pack_vector,
    request_openai_embeddings,
    require_api_key,
    utc_now,
    vector_norm,
)


DEFAULT_BATCH_SIZE = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build embeddings for exported Anki notes stored in SQLite."
    )
    parser.add_argument("--deck", required=True, help="Deck name, for example: Πες το ελληνικά")
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
        help="Optional embedding dimensions. By default the model's native size is used.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of notes per API request. Default: {DEFAULT_BATCH_SIZE}",
    )
    parser.add_argument("--limit", type=int, default=None, help="Embed at most this many notes.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild embeddings even when source content hashes have not changed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many notes need embeddings without calling OpenAI.",
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


def fetch_pending_notes(
    connection: sqlite3.Connection,
    deck: str,
    model: str,
    dim_key: str,
    limit: int | None,
    force: bool,
) -> list[sqlite3.Row]:
    where = [
        "n.deck_name = ?",
        "n.is_present = 1",
        "length(n.embedding_text) > 0",
    ]
    params: list[Any] = [deck]

    if not force:
        where.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM note_embeddings e
                WHERE e.deck_name = n.deck_name
                  AND e.note_id = n.note_id
                  AND e.embedding_model = ?
                  AND e.dimension_key = ?
                  AND e.source_content_hash = n.content_hash
            )
            """
        )
        params.extend([model, dim_key])

    sql = f"""
        SELECT n.deck_name, n.note_id, n.front_clean, n.embedding_text, n.content_hash
        FROM anki_notes n
        WHERE {' AND '.join(where)}
        ORDER BY n.note_id
    """
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    return list(connection.execute(sql, params))


def count_skipped(
    connection: sqlite3.Connection,
    deck: str,
    model: str,
    dim_key: str,
) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM anki_notes n
        WHERE n.deck_name = ?
          AND n.is_present = 1
          AND length(n.embedding_text) > 0
          AND EXISTS (
              SELECT 1
              FROM note_embeddings e
              WHERE e.deck_name = n.deck_name
                AND e.note_id = n.note_id
                AND e.embedding_model = ?
                AND e.dimension_key = ?
                AND e.source_content_hash = n.content_hash
          )
        """,
        (deck, model, dim_key),
    ).fetchone()
    return int(row["count"])


def save_embeddings(
    connection: sqlite3.Connection,
    rows: list[sqlite3.Row],
    embeddings: list[list[float]],
    model: str,
    dimensions: int | None,
    dim_key: str,
    timestamp: str,
) -> None:
    values = []
    for row, embedding in zip(rows, embeddings):
        values.append(
            {
                "deck_name": row["deck_name"],
                "note_id": int(row["note_id"]),
                "embedding_model": model,
                "dimension_key": dim_key,
                "requested_dimensions": dimensions,
                "actual_dimensions": len(embedding),
                "source_content_hash": row["content_hash"],
                "vector_blob": pack_vector(embedding),
                "vector_norm": vector_norm(embedding),
                "timestamp": timestamp,
            }
        )

    connection.executemany(
        """
        INSERT INTO note_embeddings (
            deck_name,
            note_id,
            embedding_model,
            dimension_key,
            requested_dimensions,
            actual_dimensions,
            source_content_hash,
            vector_blob,
            vector_norm,
            created_at,
            updated_at
        )
        VALUES (
            :deck_name,
            :note_id,
            :embedding_model,
            :dimension_key,
            :requested_dimensions,
            :actual_dimensions,
            :source_content_hash,
            :vector_blob,
            :vector_norm,
            :timestamp,
            :timestamp
        )
        ON CONFLICT(deck_name, note_id, embedding_model, dimension_key) DO UPDATE SET
            requested_dimensions = excluded.requested_dimensions,
            actual_dimensions = excluded.actual_dimensions,
            source_content_hash = excluded.source_content_hash,
            vector_blob = excluded.vector_blob,
            vector_norm = excluded.vector_norm,
            updated_at = excluded.updated_at
        """,
        values,
    )


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        print("error: --batch-size must be positive", file=sys.stderr)
        return 1
    if args.limit is not None and args.limit < 0:
        print("error: --limit must be non-negative", file=sys.stderr)
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
    started_at = utc_now()

    try:
        with connect_database(args.db) as connection:
            initialize_embedding_tables(connection)
            pending = fetch_pending_notes(
                connection,
                args.deck,
                model_key,
                dim_key,
                args.limit,
                args.force,
            )
            skipped = 0 if args.force else count_skipped(connection, args.deck, model_key, dim_key)

            print(f"Deck: {args.deck}")
            print(f"Database: {args.db}")
            print(f"Backend: {args.backend}")
            print(f"Model: {model}")
            print(f"Storage model key: {model_key}")
            print(f"Dimensions: {dim_key}")
            print(f"Pending: {len(pending)}")
            print(f"Already up to date: {skipped}")

            if args.dry_run or not pending:
                return 0

            api_key = require_api_key(args.api_key_env) if args.backend == "openai" else ""
            local_model = LocalEmbeddingModel(model) if args.backend == "local" else None
            embedded_count = 0
            prompt_tokens = 0
            total_tokens = 0

            for start in range(0, len(pending), args.batch_size):
                batch = pending[start : start + args.batch_size]
                texts = [row["embedding_text"] for row in batch]
                if args.backend == "local":
                    assert local_model is not None
                    embeddings = local_model.encode(texts, args.batch_size)
                    usage = {}
                else:
                    embeddings, usage = request_openai_embeddings(
                        texts,
                        model,
                        api_key,
                        dimensions=args.dimensions,
                        timeout_seconds=args.timeout,
                        ca_bundle=args.ca_bundle,
                    )
                timestamp = utc_now()
                with connection:
                    save_embeddings(
                        connection,
                        batch,
                        embeddings,
                        model_key,
                        args.dimensions,
                        dim_key,
                        timestamp,
                    )
                embedded_count += len(batch)
                prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                total_tokens += int(usage.get("total_tokens", 0) or 0)
                print(f"Embedded: {embedded_count}/{len(pending)}")

            finished_at = utc_now()
            with connection:
                connection.execute(
                    """
                    INSERT INTO embedding_runs (
                        deck_name,
                        embedding_model,
                        dimension_key,
                        requested_dimensions,
                        started_at,
                        finished_at,
                        pending_count,
                        embedded_count,
                        skipped_count,
                        prompt_tokens,
                        total_tokens
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        args.deck,
                        model_key,
                        dim_key,
                        args.dimensions,
                        started_at,
                        finished_at,
                        len(pending),
                        embedded_count,
                        skipped,
                        prompt_tokens,
                        total_tokens,
                    ),
                )

            print(f"Done: embedded {embedded_count} notes")
            if total_tokens:
                print(f"Tokens: prompt={prompt_tokens}, total={total_tokens}")
    except (EmbeddingError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
