#!/usr/bin/env python3
"""Evaluate whether existing `(не …)` targets appear among embedding neighbours."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError as error:
    raise SystemExit(
        "numpy is required for this evaluator. Run it with greekCards/.venv/bin/python."
    ) from error

from embedding_utils import (
    DEFAULT_DB_PATH,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    EmbeddingError,
    connect_database,
    dimension_key,
    embedding_model_key,
    unpack_vector,
)
from export_anki_notes import normalize_for_lookup, remove_ne_clarifications


DEFAULT_DECK = "Πες το ελληνικά"
NE_CLARIFICATION_PATTERN = re.compile(r"\(\s*не\b\s*([^)]+)\)", re.IGNORECASE)
NE_TARGET_SEPARATOR = re.compile(r"\s*,\s*(?:не\s+)?", re.IGNORECASE)
GREEK_TOKEN_PATTERN = re.compile(r"[α-ω]+")
GREEK_ARTICLES = frozenset(
    {
        "ο",
        "η",
        "το",
        "οι",
        "τα",
        "τον",
        "την",
        "τους",
        "τις",
        "του",
        "της",
        "των",
        "ένας",
        "μια",
        "μία",
        "ενα",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate top embedding candidates against existing `(не …)` card annotations."
    )
    parser.add_argument("--deck", default=DEFAULT_DECK, help=f"Deck to evaluate. Default: {DEFAULT_DECK}")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help=f"SQLite database. Default: {DEFAULT_DB_PATH}")
    parser.add_argument("--backend", choices=["local", "openai"], default="local")
    parser.add_argument("--model", help="Embedding model. Defaults depend on --backend.")
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--top", type=int, default=10, help="Candidates retained per source note. Default: 10")
    parser.add_argument("--report", type=Path, help="Write the Markdown report to this path.")
    parser.add_argument(
        "--detailed-report",
        type=Path,
        help="Write every target hit with all candidates from rank 1 through its rank.",
    )
    parser.add_argument("--json-report", type=Path, help="Write complete machine-readable results to this path.")
    return parser.parse_args()


def extract_ne_targets(*texts: str) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in NE_CLARIFICATION_PATTERN.finditer(text):
            # Both `(не A, B)` and `(не A, не B)` list separate alternatives.
            for target in NE_TARGET_SEPARATOR.split(match.group(1)):
                target = target.strip()
                if not target:
                    continue
                key = target.casefold()
                if key not in seen:
                    targets.append(target)
                    seen.add(key)
    return targets


def greek_variant(text: str) -> str:
    normalized = normalize_for_lookup(remove_ne_clarifications(text))
    return " ".join(GREEK_TOKEN_PATTERN.findall(normalized))


def articleless(text: str) -> str:
    words = text.split()
    if words and words[0] in GREEK_ARTICLES:
        return " ".join(words[1:])
    return text


def lookup_variants(text: str) -> set[str]:
    greek = greek_variant(text)
    if not greek:
        return set()
    return {greek, articleless(greek)} - {""}


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def compact(value: str, limit: int = 80) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else f"{value[: limit - 1].rstrip()}…"


def fetch_notes_and_vectors(
    connection: sqlite3.Connection,
    deck: str,
    model_key: str,
    dim_key: str,
) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT
                n.note_id,
                n.front_clean,
                n.back_clean,
                n.front_terms_json,
                e.vector_blob,
                e.vector_norm
            FROM anki_notes n
            JOIN note_embeddings e
              ON e.deck_name = n.deck_name
             AND e.note_id = n.note_id
            WHERE n.deck_name = ?
              AND n.is_present = 1
              AND e.embedding_model = ?
              AND e.dimension_key = ?
              AND e.source_content_hash = n.content_hash
            ORDER BY n.note_id
            """,
            (deck, model_key, dim_key),
        )
    )


def front_variants(row: sqlite3.Row) -> set[str]:
    terms = [str(row["front_clean"])]
    try:
        parsed_terms = json.loads(str(row["front_terms_json"]))
    except json.JSONDecodeError:
        parsed_terms = []
    if isinstance(parsed_terms, list):
        terms.extend(str(term) for term in parsed_terms)

    variants: set[str] = set()
    for term in terms:
        variants.update(lookup_variants(term))
    return variants


def build_front_index(rows: list[sqlite3.Row]) -> dict[str, set[int]]:
    index: dict[str, set[int]] = {}
    for row in rows:
        note_id = int(row["note_id"])
        for variant in front_variants(row):
            index.setdefault(variant, set()).add(note_id)
    return index


def build_front_phrase_index(rows: list[sqlite3.Row]) -> list[tuple[str, int]]:
    return [
        (greek_variant(str(row["front_clean"])), int(row["note_id"]))
        for row in rows
    ]


def contains_token_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def target_note_ids(
    target: str,
    front_index: dict[str, set[int]],
    front_phrases: list[tuple[str, int]],
) -> list[int]:
    note_ids: set[int] = set()
    for variant in lookup_variants(target):
        note_ids.update(front_index.get(variant, set()))
        note_ids.update(
            note_id
            for front_phrase, note_id in front_phrases
            if contains_token_phrase(front_phrase, variant)
        )
    return sorted(note_ids)


def model_name(args: argparse.Namespace) -> str:
    if args.model:
        return args.model
    return (
        DEFAULT_LOCAL_EMBEDDING_MODEL
        if args.backend == "local"
        else DEFAULT_OPENAI_EMBEDDING_MODEL
    )


def candidate_payload(row: sqlite3.Row, score: float, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "score": score,
        "note_id": int(row["note_id"]),
        "front": str(row["front_clean"]),
        "back": str(row["back_clean"]),
    }


def rank_candidates(
    rows: list[sqlite3.Row],
    source_indexes: list[int],
    vectors: np.ndarray,
    norms: np.ndarray,
    top: int,
) -> dict[int, list[dict[str, Any]]]:
    normalized_vectors = vectors / norms[:, np.newaxis]
    results: dict[int, list[dict[str, Any]]] = {}
    batch_size = 32
    for start in range(0, len(source_indexes), batch_size):
        batch_indexes = source_indexes[start : start + batch_size]
        scores_batch = normalized_vectors[batch_indexes] @ normalized_vectors.T
        for source_index, scores in zip(batch_indexes, scores_batch):
            scores[source_index] = -np.inf
            candidate_indexes = np.argpartition(scores, -top)[-top:]
            candidate_indexes = sorted(
                candidate_indexes,
                key=lambda index: (-float(scores[index]), int(rows[index]["note_id"])),
            )
            results[source_index] = [
                candidate_payload(rows[index], float(scores[index]), rank)
                for rank, index in enumerate(candidate_indexes, start=1)
            ]
    return results


def build_metrics(cards: list[dict[str, Any]], top: int) -> dict[str, Any]:
    cutoffs = [cutoff for cutoff in (1, 3, 5, 10) if cutoff <= top]
    if top not in cutoffs:
        cutoffs.append(top)

    mappable_cards = [card for card in cards if card["target_note_ids"]]
    mappable_targets = [
        target
        for card in cards
        for target in card["targets"]
        if target["note_ids"]
    ]
    metrics: dict[str, Any] = {
        "cards_with_ne": len(cards),
        "cards_with_mappable_targets": len(mappable_cards),
        "targets_total": sum(len(card["targets"]) for card in cards),
        "targets_mappable": len(mappable_targets),
        "source_recall": {},
        "target_recall": {},
    }
    for cutoff in cutoffs:
        source_hits = sum(
            card["first_target_rank"] is not None and card["first_target_rank"] <= cutoff
            for card in mappable_cards
        )
        target_hits = sum(
            target["rank"] is not None and target["rank"] <= cutoff
            for target in mappable_targets
        )
        metrics["source_recall"][str(cutoff)] = {"hits": source_hits, "total": len(mappable_cards)}
        metrics["target_recall"][str(cutoff)] = {"hits": target_hits, "total": len(mappable_targets)}
    return metrics


def format_rate(value: dict[str, int]) -> str:
    if value["total"] == 0:
        return "n/a"
    return f"{value['hits']}/{value['total']} ({value['hits'] / value['total']:.1%})"


def candidate_summary(card: dict[str, Any], limit: int = 3) -> str:
    return "; ".join(
        f"{candidate['front']} ({candidate['score']:.3f})"
        for candidate in card["candidates"][:limit]
    )


def card_row(card: dict[str, Any]) -> str:
    targets = ", ".join(target["raw"] for target in card["targets"])
    rank = str(card["first_target_rank"]) if card["first_target_rank"] is not None else "—"
    return (
        f"| {card['note_id']} | {markdown_cell(compact(card['front'], 52))} | "
        f"{markdown_cell(targets)} | {rank} | {markdown_cell(candidate_summary(card))} |"
    )


def markdown_report(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# Калибровка embedding-кандидатов для `(не …)`",
        "",
        f"- Колода: `{result['deck']}`",
        f"- Backend/model: `{result['backend']}` / `{result['model']}`",
        f"- Рассматриваемых кандидатов: top-{result['top']}",
        "- Оценка read-only: сопоставляются уже существующие пометки `(не …)` и ближайшие embedding-соседи.",
        "",
        "## Покрытие контрольной выборки",
        "",
        f"- Карточек с `(не …)`: {metrics['cards_with_ne']}",
        f"- Карточек хотя бы с одной сопоставимой греческой целью: {metrics['cards_with_mappable_targets']}",
        f"- Целей `(не …)`: {metrics['targets_total']}; сопоставимых с карточкой основной колоды: {metrics['targets_mappable']}",
        "",
        "| Cutoff | Попадание хотя бы одной цели на карточку | Покрытие отдельных целей |",
        "| ---: | --- | --- |",
    ]
    for cutoff, source_value in metrics["source_recall"].items():
        target_value = metrics["target_recall"][cutoff]
        lines.append(f"| {cutoff} | {format_rate(source_value)} | {format_rate(target_value)} |")

    comparable = [card for card in result["cards"] if card["target_note_ids"]]
    hits = [card for card in comparable if card["first_target_rank"] is not None]
    misses = [card for card in comparable if card["first_target_rank"] is None]
    lines.extend(
        [
            "",
            "## Примеры: ожидаемая цель попала в top",
            "",
            "| Note ID | Карточка | Уже есть `(не …)` | Первый rank цели | Первые кандидаты |",
            "| ---: | --- | --- | ---: | --- |",
        ]
    )
    lines.extend(card_row(card) for card in sorted(hits, key=lambda card: (card["first_target_rank"], card["note_id"]))[:15])
    lines.extend(
        [
            "",
            "## Примеры: ожидаемая цель не попала в top",
            "",
            "| Note ID | Карточка | Уже есть `(не …)` | Первый rank цели | Первые кандидаты |",
            "| ---: | --- | --- | ---: | --- |",
        ]
    )
    lines.extend(card_row(card) for card in sorted(misses, key=lambda card: card["note_id"])[:15])
    lines.extend(
        [
            "",
            "## Все карточки с сопоставимой целью",
            "",
            "| Note ID | Карточка | Уже есть `(не …)` | Первый rank цели | Первые кандидаты |",
            "| ---: | --- | --- | ---: | --- |",
        ]
    )
    lines.extend(card_row(card) for card in comparable)

    unmapped = result["unmapped_targets"]
    if unmapped:
        lines.extend(
            [
                "",
                "## Цели, не сопоставленные с отдельной карточкой",
                "",
                "| Цель `(не …)` | Количество |",
                "| --- | ---: |",
            ]
        )
        lines.extend(f"| {markdown_cell(target)} | {count} |" for target, count in unmapped.items())
    return "\n".join(lines) + "\n"


def detailed_markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Подробный контекст попаданий `(не …)`",
        "",
        f"- Колода: `{result['deck']}`",
        f"- Backend/model: `{result['backend']}` / `{result['model']}`",
        f"- Размер выдачи: top-{result['top']}",
        "- Каждый раздел показывает всех кандидатов с #1 до rank найденной цели.",
    ]
    target_hits = [
        (card, target)
        for card in result["cards"]
        for target in card["targets"]
        if target["rank"] is not None
    ]
    for card, target in sorted(target_hits, key=lambda item: (item[1]["rank"], item[0]["note_id"], item[1]["raw"])):
        rank = int(target["rank"])
        target_note_ids = set(target["note_ids"])
        lines.extend(
            [
                "",
                f"## {card['note_id']}: {markdown_cell(card['front'])}",
                "",
                f"- Уточнение: `(не {markdown_cell(target['raw'])})`",
                f"- Найдено на rank #{rank}",
                "",
                "| Rank | Score | Note ID | FrontText | BackText | Роль |",
                "| ---: | ---: | ---: | --- | --- | --- |",
            ]
        )
        for candidate in card["candidates"][:rank]:
            role = "← цель" if candidate["note_id"] in target_note_ids else ""
            lines.append(
                "| {rank} | {score:.4f} | {note_id} | {front} | {back} | {role} |".format(
                    rank=candidate["rank"],
                    score=candidate["score"],
                    note_id=candidate["note_id"],
                    front=markdown_cell(candidate["front"]),
                    back=markdown_cell(candidate["back"]),
                    role=role,
                )
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if args.top <= 0:
        print("error: --top must be positive", file=sys.stderr)
        return 1
    if args.dimensions is not None and args.backend == "local":
        print("error: --dimensions is only supported for --backend openai", file=sys.stderr)
        return 1

    selected_model = model_name(args)
    model_key = embedding_model_key(args.backend, selected_model)
    dim_key = dimension_key(args.dimensions)
    try:
        with connect_database(args.db) as connection:
            rows = fetch_notes_and_vectors(connection, args.deck, model_key, dim_key)
    except (EmbeddingError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not rows:
        print("error: no current embeddings found; export notes and build embeddings first", file=sys.stderr)
        return 1
    if len(rows) <= args.top:
        print("error: fewer stored vectors than requested candidates", file=sys.stderr)
        return 1

    vectors = np.vstack([np.asarray(unpack_vector(row["vector_blob"]), dtype=np.float32) for row in rows])
    norms = np.asarray([float(row["vector_norm"]) for row in rows], dtype=np.float32)
    if np.any(norms == 0):
        print("error: stored embeddings contain a zero-norm vector", file=sys.stderr)
        return 1

    front_index = build_front_index(rows)
    front_phrases = build_front_phrase_index(rows)
    source_indexes: list[int] = []
    cards: list[dict[str, Any]] = []
    unmapped_targets: Counter[str] = Counter()
    for index, row in enumerate(rows):
        raw_targets = extract_ne_targets(str(row["front_clean"]), str(row["back_clean"]))
        if not raw_targets:
            continue

        targets = []
        target_ids: set[int] = set()
        for target in raw_targets:
            note_ids = [
                note_id
                for note_id in target_note_ids(target, front_index, front_phrases)
                if note_id != int(row["note_id"])
            ]
            if not note_ids:
                unmapped_targets[target] += 1
            else:
                target_ids.update(note_ids)
            targets.append({"raw": target, "note_ids": note_ids, "rank": None})

        cards.append(
            {
                "note_id": int(row["note_id"]),
                "front": str(row["front_clean"]),
                "back": str(row["back_clean"]),
                "targets": targets,
                "target_note_ids": sorted(target_ids),
                "first_target_rank": None,
                "candidates": [],
                "source_index": index,
            }
        )
        source_indexes.append(index)

    ranked = rank_candidates(rows, source_indexes, vectors, norms, args.top)
    for card in cards:
        candidates = ranked[card["source_index"]]
        card["candidates"] = candidates
        ranks = {candidate["note_id"]: candidate["rank"] for candidate in candidates}
        target_ranks = []
        for target in card["targets"]:
            target_rank = min((ranks[note_id] for note_id in target["note_ids"] if note_id in ranks), default=None)
            target["rank"] = target_rank
            if target_rank is not None:
                target_ranks.append(target_rank)
        card["first_target_rank"] = min(target_ranks, default=None)
        del card["source_index"]

    result = {
        "deck": args.deck,
        "backend": args.backend,
        "model": selected_model,
        "storage_model_key": model_key,
        "dimensions": dim_key,
        "top": args.top,
        "metrics": build_metrics(cards, args.top),
        "cards": cards,
        "unmapped_targets": dict(sorted(unmapped_targets.items(), key=lambda item: (-item[1], item[0]))),
    }
    rendered_markdown = markdown_report(result)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered_markdown, encoding="utf-8")
        print(f"Markdown report: {args.report}")
    else:
        print(rendered_markdown, end="")
    if args.detailed_report:
        args.detailed_report.parent.mkdir(parents=True, exist_ok=True)
        args.detailed_report.write_text(detailed_markdown_report(result), encoding="utf-8")
        print(f"Detailed Markdown report: {args.detailed_report}")
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"JSON report: {args.json_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
