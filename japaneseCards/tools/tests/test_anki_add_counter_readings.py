from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import anki_add  # noqa: E402


CATALOG = {
    "numeric_characters": "一二三四五六七八九十何幾",
    "counter_suffix_exceptions": ["人"],
}


def note(surface: str, kana: str, model: str = anki_add.KANJI_MODEL) -> dict:
    return {
        "modelName": model,
        "fields": {"Kanji": surface, "Kana": kana},
    }


def result(
    *,
    reading: str,
    needs_review: bool = False,
    complete: bool = True,
    pos: str = "接尾辞-名詞的-助数詞",
) -> dict:
    return {
        "complete": complete,
        "needs_review": needs_review,
        "errors": {} if complete else {"bccwj": "missing index"},
        "candidates": [
            {
                "reading": reading,
                "spellings": [reading],
                "plausible": True,
            }
        ],
        "sources": {"unidic": {"nodes": [{"pos": pos}]}},
    }


class CounterReadingPreflightTest(unittest.TestCase):
    @staticmethod
    def phoneme_key(reading: str) -> str:
        return reading.replace("ー", "お")

    def validate(self, notes, lookup, reviews=None):
        return anki_add.validate_counter_readings(
            notes,
            reviews=reviews,
            lookup=lookup,
            phoneme_key=self.phoneme_key,
            catalog=CATALOG,
        )

    def test_unambiguous_counter_is_accepted(self) -> None:
        checked = self.validate(
            [note("一本", "いっぽん")],
            lambda _surface: result(reading="いっぽん"),
        )
        self.assertEqual(
            [
                {
                    "surface": "一本",
                    "kana": "いっぽん",
                    "counter": True,
                    "reviewed": False,
                }
            ],
            checked,
        )

    def test_wrong_kana_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "未確認|Неверное|подтверждённое"):
            self.validate(
                [note("一本", "いちほん")],
                lambda _surface: result(reading="いっぽん"),
            )

    def test_ambiguous_counter_is_blocked_without_review(self) -> None:
        with self.assertRaisesRegex(ValueError, "требует обсуждения"):
            self.validate(
                [note("七年", "ななねん")],
                lambda _surface: result(reading="ななねん", needs_review=True),
            )

    def test_explicit_review_accepts_selected_candidate(self) -> None:
        checked = self.validate(
            [note("七年", "ななねん")],
            lambda _surface: result(reading="ななねん", needs_review=True),
            reviews={
                "七年": {
                    "kana": "ななねん",
                    "reason": "Пользователь выбрал частотный вариант после обсуждения.",
                }
            },
        )
        self.assertTrue(checked[0]["reviewed"])

    def test_ordinary_kanji_card_does_not_call_lookup(self) -> None:
        def unexpected_lookup(_surface):
            self.fail("lookup must not run for an ordinary kanji card")

        self.assertEqual([], self.validate([note("不思議", "ふしぎ")], unexpected_lookup))

    def test_numeric_non_counter_still_has_its_reading_checked(self) -> None:
        self.assertEqual(
            [
                {
                    "surface": "一緒",
                    "kana": "いっしょ",
                    "counter": False,
                    "reviewed": False,
                }
            ],
            self.validate(
                [note("一緒", "いっしょ")],
                lambda _surface: result(
                    reading="いっしょ",
                    pos="名詞-普通名詞-サ変可能",
                ),
            ),
        )

    def test_incomplete_evidence_is_never_overridden(self) -> None:
        with self.assertRaisesRegex(ValueError, "нельзя проверить полностью"):
            self.validate(
                [note("一本", "いっぽん")],
                lambda _surface: result(reading="いっぽん", complete=False),
                reviews={"一本": {"kana": "いっぽん", "reason": "manual"}},
            )


if __name__ == "__main__":
    unittest.main()
