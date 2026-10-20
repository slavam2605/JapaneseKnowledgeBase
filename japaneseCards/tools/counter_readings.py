#!/usr/bin/env python3
"""Collect reading evidence for Japanese number/counter expressions.

This is an evidence collector, not a normative oracle.  It combines:

* exact long-unit and component frequencies from BCCWJ;
* the best morphological analysis from UniDic;
* Open JTalk's deterministic G2P result;
* exact JMdict readings when the complete expression has an entry.

Ambiguous results are deliberately surfaced through ``needs_review``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
RESOURCES = REPO_ROOT / "resources"
COUNTER_RESOURCES = RESOURCES / "counter_readings"
BCCWJ_DB = HERE / "counter_readings_index.sqlite"
JMDICT_DB = HERE / "dict_index.sqlite"
UNIDIC_DIR = COUNTER_RESOURCES / "unidic-cwj-202512"
OPEN_JTALK_DIR = COUNTER_RESOURCES / "open_jtalk_dic_utf_8-1.11"


def katakana_to_hiragana(text: str) -> str:
    """Normalize ordinary katakana to hiragana, preserving punctuation."""
    output = []
    for character in text:
        codepoint = ord(character)
        if 0x30A1 <= codepoint <= 0x30F6:
            output.append(chr(codepoint - 0x60))
        else:
            output.append(character)
    return "".join(output)


def parse_unidic_features(raw: str) -> list[str]:
    return next(csv.reader([raw]))


def lookup_unidic(surface: str) -> dict[str, Any]:
    if not UNIDIC_DIR.exists():
        raise FileNotFoundError(f"UniDic directory is missing: {UNIDIC_DIR}")
    try:
        import MeCab
    except ImportError as error:
        raise RuntimeError(
            "MeCab is not installed; use japaneseCards/.venv/bin/python"
        ) from error

    # MeCab parses its option string itself, so the path must remain quoted.
    options = f'-r /dev/null -d "{UNIDIC_DIR}"'
    tagger = MeCab.Tagger(options)
    node = tagger.parseToNode(surface)
    nodes = []
    reading_parts = []

    while node is not None:
        if node.surface:
            features = parse_unidic_features(node.feature)
            if len(features) < 12:
                raise RuntimeError(
                    f"Unexpected UniDic feature count for {node.surface!r}: {features}"
                )
            # UniDic 2025-12's dicrc/chamame2 format identifies F[9] as 発音形.
            # The comment in feature.def lists a different order, so use the
            # actual dictionary output contract rather than that stale comment.
            pronunciation = features[9] if features[9] != "*" else node.surface
            reading_parts.append(pronunciation)
            nodes.append(
                {
                    "surface": node.surface,
                    "lemma": features[7],
                    "lemma_reading": katakana_to_hiragana(features[6]),
                    "pronunciation": katakana_to_hiragana(pronunciation),
                    "pos": "-".join(item for item in features[0:4] if item != "*"),
                }
            )
        node = node.next

    return {
        "version": "2025.12",
        "reading": katakana_to_hiragana("".join(reading_parts)),
        "nodes": nodes,
    }


def lookup_open_jtalk(surface: str) -> dict[str, Any]:
    if not OPEN_JTALK_DIR.exists():
        raise FileNotFoundError(f"Open JTalk dictionary is missing: {OPEN_JTALK_DIR}")

    os.environ.setdefault("OPEN_JTALK_DICT_DIR", str(OPEN_JTALK_DIR))
    try:
        import pyopenjtalk
    except ImportError as error:
        raise RuntimeError(
            "pyopenjtalk-plus is not installed; use japaneseCards/.venv/bin/python"
        ) from error

    return {
        "version": pyopenjtalk.__version__,
        "reading": katakana_to_hiragana(pyopenjtalk.g2p(surface, kana=True)),
        "phones": pyopenjtalk.g2p(surface),
    }


def reading_phonemes(reading: str) -> str:
    """Return a phonetic key so とおか and とーか merge as one reading."""
    os.environ.setdefault("OPEN_JTALK_DICT_DIR", str(OPEN_JTALK_DIR))
    import pyopenjtalk

    return pyopenjtalk.g2p(reading)


def lookup_jmdict(surface: str) -> dict[str, Any]:
    if not JMDICT_DB.exists():
        raise FileNotFoundError(
            f"JMdict index is missing: {JMDICT_DB}; run dict_build_index.py"
        )

    connection = sqlite3.connect(JMDICT_DB)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT w.reading, w.readings
            FROM word w
            JOIN form f ON f.word_id = w.id
            WHERE f.surface = ?
            """,
            (surface,),
        ).fetchall()
    finally:
        connection.close()

    readings = []
    for row in rows:
        for reading in json.loads(row["readings"]):
            if reading not in readings:
                readings.append(reading)
    return {"found": bool(rows), "readings": readings}


def aggregate_bccwj_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        reading = katakana_to_hiragana(row["reading"])
        item = grouped.setdefault(
            reading,
            {
                "reading": reading,
                "frequency": 0,
                "pmw": 0.0,
                "core_frequency": 0,
                "best_rank": None,
                "analyses": [],
            },
        )
        item["frequency"] += row["frequency"]
        item["pmw"] += row["pmw"]
        item["core_frequency"] += row["core_frequency"] or 0
        if row["rank"] is not None:
            item["best_rank"] = min(item["best_rank"] or row["rank"], row["rank"])
        item["analyses"].append(
            {
                "pos": row["pos"],
                "word_type": row["word_type"],
                "frequency": row["frequency"],
                "rank": row["rank"],
            }
        )

    result = list(grouped.values())
    for item in result:
        item["pmw"] = round(item["pmw"], 7)
    result.sort(key=lambda item: (-item["frequency"], item["reading"]))
    return result


def lookup_bccwj_exact(
    connection: sqlite3.Connection, source: str, lemma: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT rank, reading, pos, word_type, frequency, pmw, core_frequency
        FROM frequency
        WHERE source = ? AND lemma = ?
        """,
        (source, lemma),
    ).fetchall()
    return aggregate_bccwj_rows(rows)


def frequency_assessment(readings: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [item for item in readings if item["frequency"] > 0]
    total = sum(item["frequency"] for item in observed)
    if not observed:
        return {"status": "unattested", "total": 0, "dominant": None, "ratio": None}
    if total < 20:
        return {"status": "sparse", "total": total, "dominant": None, "ratio": None}

    top = observed[0]
    second_frequency = observed[1]["frequency"] if len(observed) > 1 else 0
    ratio = None if second_frequency == 0 else top["frequency"] / second_frequency
    if second_frequency == 0 or ratio >= 5:
        return {
            "status": "dominant",
            "total": total,
            "dominant": top["reading"],
            "ratio": None if ratio is None else round(ratio, 2),
        }
    return {
        "status": "comparable",
        "total": total,
        "dominant": None,
        "ratio": round(ratio, 2),
    }


def collect_candidates(
    bccwj: list[dict[str, Any]],
    unidic: dict[str, Any] | None,
    open_jtalk: dict[str, Any] | None,
    jmdict: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in bccwj:
        evidence.append(
            {
                "reading": item["reading"],
                "source": "bccwj_luw",
                "frequency": item["frequency"],
                "pmw": item["pmw"],
                "core_frequency": item["core_frequency"],
            }
        )

    model_readings = (
        ("unidic", unidic["reading"] if unidic else None),
        ("open_jtalk", open_jtalk["reading"] if open_jtalk else None),
    )
    for source, reading in model_readings:
        if reading:
            evidence.append(
                {
                    "reading": reading,
                    "source": source,
                    "frequency": 0,
                    "pmw": 0.0,
                    "core_frequency": 0,
                }
            )

    if jmdict:
        for reading in jmdict["readings"]:
            evidence.append(
                {
                    "reading": reading,
                    "source": "jmdict",
                    "frequency": 0,
                    "pmw": 0.0,
                    "core_frequency": 0,
                }
            )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        try:
            key = reading_phonemes(item["reading"]) if open_jtalk else item["reading"]
        except Exception:
            key = item["reading"]
        grouped[key].append(item)

    source_priority = {"jmdict": 0, "bccwj_luw": 1, "unidic": 2, "open_jtalk": 3}
    result = []
    for items in grouped.values():
        canonical = min(
            items,
            key=lambda item: (
                source_priority[item["source"]],
                -item["frequency"],
                item["reading"],
            ),
        )["reading"]
        sources = []
        for item in items:
            if item["source"] not in sources:
                sources.append(item["source"])
        spellings = sorted({item["reading"] for item in items})
        result.append(
            {
                "reading": canonical,
                "spellings": spellings,
                "bccwj_frequency": sum(item["frequency"] for item in items),
                "bccwj_pmw": round(sum(item["pmw"] for item in items), 7),
                "bccwj_core_frequency": sum(
                    item["core_frequency"] for item in items
                ),
                "sources": sources,
            }
        )

    for item in result:
        item["plausible"] = (
            item["bccwj_core_frequency"] > 0
            or any(source in item["sources"] for source in ("unidic", "open_jtalk", "jmdict"))
        )
    result.sort(key=lambda item: (-item["bccwj_frequency"], item["reading"]))
    return result


def assessment_from_candidates(
    candidates: list[dict[str, Any]], plausible_only: bool
) -> dict[str, Any]:
    readings = [
        {"reading": item["reading"], "frequency": item["bccwj_frequency"]}
        for item in candidates
        if not plausible_only or item["plausible"]
    ]
    readings.sort(key=lambda item: (-item["frequency"], item["reading"]))
    return frequency_assessment(readings)


def lookup(surface: str) -> dict[str, Any]:
    errors: dict[str, str] = {}

    try:
        unidic = lookup_unidic(surface)
    except Exception as error:
        unidic = None
        errors["unidic"] = str(error)

    try:
        open_jtalk = lookup_open_jtalk(surface)
    except Exception as error:
        open_jtalk = None
        errors["open_jtalk"] = str(error)

    try:
        jmdict = lookup_jmdict(surface)
    except Exception as error:
        jmdict = None
        errors["jmdict"] = str(error)

    bccwj_exact: list[dict[str, Any]] = []
    components = []
    try:
        if not BCCWJ_DB.exists():
            raise FileNotFoundError(
                f"BCCWJ index is missing: {BCCWJ_DB}; run counter_readings_build_index.py"
            )
        connection = sqlite3.connect(BCCWJ_DB)
        connection.row_factory = sqlite3.Row
        try:
            bccwj_exact = lookup_bccwj_exact(connection, "luw", surface)
            if unidic:
                for node in unidic["nodes"]:
                    components.append(
                        {
                            "surface": node["surface"],
                            "lemma": node["lemma"],
                            "readings": lookup_bccwj_exact(
                                connection, "suw", node["lemma"]
                            ),
                        }
                    )
        finally:
            connection.close()
    except Exception as error:
        errors["bccwj"] = str(error)

    candidates = collect_candidates(bccwj_exact, unidic, open_jtalk, jmdict)
    plausible = [item for item in candidates if item["plausible"]]
    top_corpus_frequency = max(
        (item["bccwj_frequency"] for item in candidates), default=0
    )
    unsupported_corpus_signals = [
        item["reading"]
        for item in candidates
        if not item["plausible"]
        and item["bccwj_frequency"] >= 20
        and top_corpus_frequency > 0
        and item["bccwj_frequency"] / top_corpus_frequency >= 0.05
    ]
    model_conflict = bool(
        unidic
        and open_jtalk
        and reading_phonemes(unidic["reading"])
        != reading_phonemes(open_jtalk["reading"])
    )

    return {
        "surface": surface,
        "complete": not errors,
        "needs_review": (
            len(plausible) != 1 or model_conflict or bool(unsupported_corpus_signals)
        ),
        "model_conflict": model_conflict,
        "unsupported_corpus_signals": unsupported_corpus_signals,
        "candidates": candidates,
        "frequency_assessment": {
            "supported": assessment_from_candidates(candidates, plausible_only=True),
            "raw": assessment_from_candidates(candidates, plausible_only=False),
        },
        "sources": {
            "bccwj_luw": bccwj_exact,
            "bccwj_suw_components": components,
            "unidic": unidic,
            "open_jtalk": open_jtalk,
            "jmdict": jmdict,
        },
        "errors": errors,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect reading and frequency evidence for full Japanese expressions."
    )
    parser.add_argument("surfaces", nargs="+", help="Full forms, e.g. 七年 一本 何人")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a compact human-readable report instead of JSON.",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Exit with status 2 when any result is incomplete or ambiguous.",
    )
    return parser.parse_args(argv)


def print_summary(results: list[dict[str, Any]]) -> None:
    for index, result in enumerate(results):
        if index:
            print()
        status = "REVIEW" if result["needs_review"] else "OK"
        complete = "complete" if result["complete"] else "incomplete"
        print(f"{result['surface']}: {status} ({complete})")
        for candidate in result["candidates"]:
            marker = "*" if candidate["plausible"] else "-"
            sources = ", ".join(candidate["sources"])
            print(
                f"  {marker} {candidate['reading']}: "
                f"BCCWJ={candidate['bccwj_frequency']} "
                f"(core={candidate['bccwj_core_frequency']}); {sources}"
            )
        assessment = result["frequency_assessment"]["supported"]
        if assessment["dominant"]:
            print(
                f"  corpus: {assessment['status']} {assessment['dominant']} "
                f"(ratio={assessment['ratio']})"
            )
        else:
            print(f"  corpus supported: {assessment['status']} (total={assessment['total']})")
        raw = result["frequency_assessment"]["raw"]
        if result["unsupported_corpus_signals"]:
            print(
                f"  corpus raw: {raw['status']} "
                f"(dominant={raw['dominant']}, total={raw['total']}, ratio={raw['ratio']})"
            )
        if result["unsupported_corpus_signals"]:
            print(
                "  unsupported corpus signal: "
                + ", ".join(result["unsupported_corpus_signals"])
            )
        if result["errors"]:
            for source, error in result["errors"].items():
                print(f"  ERROR {source}: {error}")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    results = [lookup(surface) for surface in args.surfaces]
    if args.summary:
        print_summary(results)
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.fail_on_review and any(
        not item["complete"] or item["needs_review"] for item in results
    ):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
