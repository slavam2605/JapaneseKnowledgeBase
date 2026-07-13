"""Shared helpers for local embedding storage and search."""

from __future__ import annotations

import array
import json
import math
import os
import ssl
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "anki_index.sqlite3"
DEFAULT_BACKEND = "local"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_LOCAL_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_EMBEDDING_MODEL = DEFAULT_LOCAL_EMBEDDING_MODEL
DEFAULT_OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
EMBEDDING_BACKENDS = {"openai", "local"}


class EmbeddingError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dimension_key(dimensions: int | None) -> str:
    return str(dimensions) if dimensions is not None else "default"


def validate_backend(backend: str) -> None:
    if backend not in EMBEDDING_BACKENDS:
        supported = ", ".join(sorted(EMBEDDING_BACKENDS))
        raise EmbeddingError(f"Unsupported embedding backend {backend!r}. Use one of: {supported}.")


def embedding_model_key(backend: str, model: str) -> str:
    validate_backend(backend)
    return f"{backend}:{model}"


def connect_database(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_embedding_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS note_embeddings (
            deck_name TEXT NOT NULL,
            note_id INTEGER NOT NULL,
            embedding_model TEXT NOT NULL,
            dimension_key TEXT NOT NULL,
            requested_dimensions INTEGER,
            actual_dimensions INTEGER NOT NULL,
            source_content_hash TEXT NOT NULL,
            vector_blob BLOB NOT NULL,
            vector_norm REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (deck_name, note_id, embedding_model, dimension_key),
            FOREIGN KEY (deck_name, note_id)
                REFERENCES anki_notes(deck_name, note_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_note_embeddings_lookup
            ON note_embeddings(deck_name, embedding_model, dimension_key);

        CREATE TABLE IF NOT EXISTS embedding_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_name TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            dimension_key TEXT NOT NULL,
            requested_dimensions INTEGER,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            pending_count INTEGER NOT NULL,
            embedded_count INTEGER NOT NULL,
            skipped_count INTEGER NOT NULL,
            prompt_tokens INTEGER,
            total_tokens INTEGER
        );
        """
    )


def require_api_key(env_var_name: str) -> str:
    api_key = os.environ.get(env_var_name)
    if not api_key:
        raise EmbeddingError(
            f"{env_var_name} is not set. Create an OpenAI API key and run "
            f"`export {env_var_name}=...` before building embeddings."
        )
    return api_key


def create_ssl_context(ca_bundle: str | None = None) -> ssl.SSLContext | None:
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)

    env_ca_bundle = os.environ.get("SSL_CERT_FILE")
    if env_ca_bundle:
        return ssl.create_default_context(cafile=env_ca_bundle)

    try:
        import certifi  # type: ignore[import-not-found]
    except ImportError:
        return None

    return ssl.create_default_context(cafile=certifi.where())


def is_certificate_error(error: urllib.error.URLError) -> bool:
    reason = getattr(error, "reason", None)
    if isinstance(reason, ssl.SSLCertVerificationError):
        return True
    return "CERTIFICATE_VERIFY_FAILED" in str(error)


def certificate_error_message(error: urllib.error.URLError) -> str:
    return (
        "TLS certificate verification failed while connecting to OpenAI. "
        "Try one of these fixes:\n"
        "  1. If this is python.org Python on macOS, run "
        "`/Applications/Python 3.x/Install Certificates.command`.\n"
        "  2. Install certifi for this Python: `python3 -m pip install certifi`.\n"
        "  3. Or pass a CA bundle explicitly: `--ca-bundle /path/to/cacert.pem` "
        "or set `SSL_CERT_FILE=/path/to/cacert.pem`.\n"
        f"Original error: {error}"
    )


def request_openai_embeddings(
    texts: list[str],
    model: str,
    api_key: str,
    dimensions: int | None = None,
    url: str = DEFAULT_OPENAI_EMBEDDINGS_URL,
    timeout_seconds: float = 60.0,
    max_retries: int = 3,
    ca_bundle: str | None = None,
) -> tuple[list[list[float]], dict[str, Any]]:
    if not texts:
        return [], {}

    payload: dict[str, Any] = {
        "model": model,
        "input": texts,
        "encoding_format": "float",
    }
    if dimensions is not None:
        payload["dimensions"] = dimensions

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    ssl_context = create_ssl_context(ca_bundle)

    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
                context=ssl_context,
            ) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            data = parsed.get("data", [])
            embeddings_by_index = sorted(data, key=lambda item: item["index"])
            embeddings = [item["embedding"] for item in embeddings_by_index]
            if len(embeddings) != len(texts):
                raise EmbeddingError(
                    f"OpenAI returned {len(embeddings)} embeddings for {len(texts)} inputs."
                )
            return embeddings, parsed.get("usage", {})
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            if error.code in {429, 500, 502, 503, 504} and attempt < max_retries:
                time.sleep(2**attempt)
                continue
            raise EmbeddingError(
                f"OpenAI embeddings request failed with HTTP {error.code}: {error_body}"
            ) from error
        except urllib.error.URLError as error:
            if is_certificate_error(error):
                raise EmbeddingError(certificate_error_message(error)) from error
            if attempt < max_retries:
                time.sleep(2**attempt)
                continue
            raise EmbeddingError(f"Could not reach OpenAI embeddings API: {error}") from error

    raise EmbeddingError("OpenAI embeddings request failed after retries.")


class LocalEmbeddingModel:
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise EmbeddingError(
                "Local embeddings require sentence-transformers. Install it with:\n"
                "  python3 -m pip install -r requirements-local-embeddings.txt"
            ) from error

        self.model_name = model_name
        try:
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            try:
                self.model = SentenceTransformer(model_name)
            except Exception as error:
                raise EmbeddingError(
                    f"Could not load local embedding model {model_name!r}. "
                    "On the first run this downloads the model from Hugging Face; "
                    "after that it can run from the local cache."
                ) from error

    def encode(self, texts: list[str], batch_size: int) -> list[list[float]]:
        if not texts:
            return []
        try:
            encoded = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as error:
            raise EmbeddingError(f"Local embedding model {self.model_name!r} failed: {error}") from error

        result: list[list[float]] = []
        for embedding in encoded:
            if hasattr(embedding, "tolist"):
                result.append([float(value) for value in embedding.tolist()])
            else:
                result.append([float(value) for value in embedding])
        return result


def pack_vector(vector: list[float]) -> bytes:
    packed = array.array("f", vector)
    return packed.tobytes()


def unpack_vector(vector_blob: bytes) -> array.array[float]:
    vector = array.array("f")
    vector.frombytes(vector_blob)
    return vector


def vector_norm(vector: list[float] | array.array[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def cosine_similarity(
    left: list[float] | array.array[float],
    left_norm: float,
    right: list[float] | array.array[float],
    right_norm: float,
) -> float:
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right)) / (
        left_norm * right_norm
    )


def compact_text(text: str, max_length: int) -> str:
    compacted = " ".join(text.split())
    if len(compacted) <= max_length:
        return compacted
    return compacted[: max_length - 1].rstrip() + "…"
