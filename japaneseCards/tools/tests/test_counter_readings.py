from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import counter_readings  # noqa: E402


class CounterReadingsTest(unittest.TestCase):
    def test_katakana_to_hiragana(self) -> None:
        self.assertEqual("ななねん", counter_readings.katakana_to_hiragana("ナナネン"))
        self.assertEqual("すーぱー", counter_readings.katakana_to_hiragana("スーパー"))

    def test_frequency_assessment(self) -> None:
        assessment = counter_readings.frequency_assessment(
            [
                {"reading": "ななねん", "frequency": 1890},
                {"reading": "しちねん", "frequency": 6},
            ]
        )
        self.assertEqual("dominant", assessment["status"])
        self.assertEqual("ななねん", assessment["dominant"])
        self.assertEqual(315.0, assessment["ratio"])

    def test_nananen_surfaces_real_source_disagreement(self) -> None:
        result = counter_readings.lookup("七年")
        self.assertTrue(result["complete"])
        self.assertTrue(result["needs_review"])
        self.assertTrue(result["model_conflict"])
        self.assertEqual("しちねん", result["sources"]["unidic"]["reading"])
        self.assertEqual("ななねん", result["sources"]["open_jtalk"]["reading"])

        by_reading = {item["reading"]: item for item in result["candidates"]}
        self.assertEqual(1890, by_reading["ななねん"]["bccwj_frequency"])
        self.assertEqual(6, by_reading["しちねん"]["bccwj_frequency"])
        self.assertTrue(by_reading["ななねん"]["plausible"])
        self.assertTrue(by_reading["しちねん"]["plausible"])
        self.assertFalse(by_reading["ななとせ"]["plausible"])

    def test_ippon_is_unambiguous_after_corpus_noise_filtering(self) -> None:
        result = counter_readings.lookup("一本")
        plausible = [item for item in result["candidates"] if item["plausible"]]
        self.assertFalse(result["needs_review"])
        self.assertEqual(["いっぽん"], [item["reading"] for item in plausible])
        self.assertEqual(
            {"bccwj_luw", "unidic", "open_jtalk", "jmdict"},
            set(plausible[0]["sources"]),
        )

    def test_nannen_agrees_across_all_sources(self) -> None:
        result = counter_readings.lookup("何年")
        plausible = [item for item in result["candidates"] if item["plausible"]]
        self.assertFalse(result["needs_review"])
        self.assertEqual(["なんねん"], [item["reading"] for item in plausible])

    def test_long_vowel_spellings_merge_by_pronunciation(self) -> None:
        result = counter_readings.lookup("十日")
        plausible = [item for item in result["candidates"] if item["plausible"]]
        self.assertFalse(result["needs_review"])
        self.assertEqual(["とおか"], [item["reading"] for item in plausible])
        self.assertEqual(
            ["とおか", "とーか"],
            plausible[0]["spellings"],
        )


if __name__ == "__main__":
    unittest.main()
