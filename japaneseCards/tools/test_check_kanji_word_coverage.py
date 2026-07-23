#!/usr/bin/env python3
"""Focused checks for check_kanji_word_coverage.py."""

from __future__ import annotations

import unittest

from check_kanji_word_coverage import IndexedNote, has_tag, scan, summary


def note(note_id: int, written: str, reading: str, vector: list[float]) -> IndexedNote:
    return IndexedNote(
        note_id=note_id,
        deck_name="test",
        front=written,
        meaning="meaning",
        written=written,
        reading=reading,
        vector=vector,
        vector_norm=1.0,
    )


class CoverageTest(unittest.TestCase):
    def test_to_review_matches_hierarchical_tag(self) -> None:
        self.assertTrue(has_tag('["ai_generated", "ai_generated::to_review"]', "to_review"))
        self.assertTrue(has_tag('["ai_generated::to_review"]', "ai_generated::to_review"))
        self.assertFalse(has_tag('["ai_generated::deduped"]', "to_review"))

    def test_empty_review_scope_is_a_valid_result(self) -> None:
        counts = summary(scan([], [note(2, "電気", "でんき", [1.0, 0.0])], 1, 0.8))
        self.assertTrue(all(count == 0 for count in counts.values()))

    def test_exact_form_is_covered(self) -> None:
        results = scan(
            [note(1, "電気", "でんき", [1.0, 0.0])],
            [note(2, "電気", "でんき", [1.0, 0.0])],
            top=1,
            review_threshold=0.8,
        )
        self.assertEqual("COVERED_EXACT", results[0]["status"])

    def test_phrase_requires_both_writing_and_reading(self) -> None:
        results = scan(
            [note(1, "電気", "でんき", [1.0, 0.0])],
            [note(2, "電気をつける", "でんきをつける", [1.0, 0.0])],
            top=1,
            review_threshold=0.8,
        )
        self.assertEqual("COVERED_IN_PHRASE", results[0]["status"])

        results = scan(
            [note(1, "来る", "くる", [1.0, 0.0])],
            [note(2, "出来る", "できる", [0.0, 1.0])],
            top=1,
            review_threshold=0.8,
        )
        self.assertEqual("MISSING", results[0]["status"])

    def test_semantic_match_needs_review(self) -> None:
        results = scan(
            [note(1, "付ける", "つける", [1.0, 0.0])],
            [note(2, "電気をつける", "でんきをつける", [1.0, 0.0])],
            top=1,
            review_threshold=0.8,
        )
        self.assertEqual("REVIEW_SEMANTIC", results[0]["status"])
        self.assertEqual(2, results[0]["matches"][0]["note_id"])


if __name__ == "__main__":
    unittest.main()
