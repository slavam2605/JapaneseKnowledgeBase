#!/usr/bin/env python3
"""Build a compact SQLite lookup index from the BCCWJ frequency tables.

The source TSV files stay inside their ZIP archives under
``resources/counter_readings/raw``.  This script streams them and keeps only
the columns needed to compare readings of an exact written form.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
RAW_DIR = REPO_ROOT / "resources" / "counter_readings" / "raw"
DB_PATH = HERE / "counter_readings_index.sqlite"

SOURCES = {
    "suw": RAW_DIR / "BCCWJ_frequencylist_suw_ver1_0.zip",
    "luw": RAW_DIR / "BCCWJ_frequencylist_luw_ver1_0.zip",
}

KEPT_COLUMNS = (
    "rank",
    "lForm",
    "lemma",
    "pos",
    "subLemma",
    "wType",
    "frequency",
    "pmw",
    "core_frequency",
    "core_pmw",
)


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def as_int(value: str) -> int | None:
    return int(value) if value else None


def as_float(value: str) -> float | None:
    return float(value) if value else None


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE frequency(
            source         TEXT NOT NULL,
            rank           INTEGER,
            reading        TEXT NOT NULL,
            lemma          TEXT NOT NULL,
            pos            TEXT,
            sublemma       TEXT,
            word_type      TEXT,
            frequency      INTEGER NOT NULL,
            pmw            REAL NOT NULL,
            core_frequency INTEGER,
            core_pmw       REAL
        );
        CREATE TABLE dataset(
            source TEXT PRIMARY KEY,
            archive TEXT NOT NULL,
            rows INTEGER NOT NULL
        );
        """
    )


def archive_member(archive: zipfile.ZipFile) -> str:
    files = [item.filename for item in archive.infolist() if not item.is_dir()]
    if len(files) != 1 or not files[0].endswith(".tsv"):
        raise RuntimeError(f"Expected one TSV in archive, found: {files}")
    return files[0]


def import_source(
    connection: sqlite3.Connection, source: str, archive_path: Path
) -> int:
    log(f"Importing {source}: {archive_path.name}")
    inserted = 0
    batch: list[tuple[object, ...]] = []

    with zipfile.ZipFile(archive_path) as archive:
        member = archive_member(archive)
        with archive.open(member) as binary:
            header = binary.readline().decode("utf-8").rstrip("\r\n").split("\t")
            indexes = {name: header.index(name) for name in KEPT_COLUMNS}

            for raw_line in binary:
                values = raw_line.decode("utf-8").rstrip("\r\n").split("\t")
                batch.append(
                    (
                        source,
                        as_int(values[indexes["rank"]]),
                        values[indexes["lForm"]],
                        values[indexes["lemma"]],
                        values[indexes["pos"]],
                        values[indexes["subLemma"]],
                        values[indexes["wType"]],
                        as_int(values[indexes["frequency"]]) or 0,
                        as_float(values[indexes["pmw"]]) or 0.0,
                        as_int(values[indexes["core_frequency"]]),
                        as_float(values[indexes["core_pmw"]]),
                    )
                )
                if len(batch) >= 20_000:
                    connection.executemany(
                        "INSERT INTO frequency VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch
                    )
                    inserted += len(batch)
                    batch.clear()
                    if inserted % 200_000 == 0:
                        log(f"  {source}: {inserted:,} rows")

    if batch:
        connection.executemany(
            "INSERT INTO frequency VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch
        )
        inserted += len(batch)

    connection.execute(
        "INSERT INTO dataset(source, archive, rows) VALUES (?,?,?)",
        (source, archive_path.name, inserted),
    )
    log(f"  {source}: {inserted:,} rows imported")
    return inserted


def build_index(db_path: Path = DB_PATH) -> None:
    missing = [path for path in SOURCES.values() if not path.exists()]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Missing BCCWJ archives:\n{formatted}")

    temporary = db_path.with_suffix(db_path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()

    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            PRAGMA temp_store=MEMORY;
            """
        )
        create_schema(connection)
        for source, archive_path in SOURCES.items():
            import_source(connection, source, archive_path)
        log("Creating lookup indexes...")
        connection.executescript(
            """
            CREATE INDEX idx_frequency_source_lemma
                ON frequency(source, lemma);
            CREATE INDEX idx_frequency_source_reading
                ON frequency(source, reading);
            """
        )
        connection.commit()
        connection.execute("ANALYZE")
        connection.commit()
    finally:
        connection.close()

    os.replace(temporary, db_path)
    log(f"Ready: {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    try:
        build_index()
    except Exception as error:
        log(f"ERROR: {error}")
        raise
