#!/usr/bin/env python3
"""Достаёт JLPT-уровень и common-флаг японских слов с jisho.org (JSON API).

Использование:
    python3 jisho_levels.py 銀行 たぶん 切符 ...
    echo '銀行\nたぶん' | python3 jisho_levels.py -   # по одному слову на строку

Вывод — JSON-массив объектов:
    {word, slug, common, jlpt, jlpt_tag, matched}
где:
  - jlpt     — все уровни, что вернул jisho (напр. ["jlpt-n3","jlpt-n5"]);
  - jlpt_tag — рекомендуемый тег по САМОМУ ЛЁГКОМУ уровню ("jlpt::n5") или null;
  - common   — true/false (jisho is_common) или null, если слово не найдено;
  - matched  — "exact" (нашли точное совпадение формы/чтения),
               "first" (точного нет, взят первый результат — ПРОВЕРИТЬ ВРУЧНУЮ),
               "none"  (ничего не найдено).

Не делает запросов к Anki — только справка с jisho. Зависимости: curl + python3.
"""
import sys
import json
import time
import subprocess
import urllib.parse


def fetch(word):
    url = "https://jisho.org/api/v1/search/words?keyword=" + urllib.parse.quote(word)
    out = subprocess.run(
        ["curl", "-s", "--max-time", "20", url],
        capture_output=True, text=True, timeout=25,
    ).stdout
    if not out.strip():
        return []
    return json.loads(out).get("data", [])


def pick(word, data):
    """Выбрать запись, точно совпадающую по slug/форме/чтению; иначе первую."""
    for entry in data:
        forms = {entry.get("slug", "")}
        for jp in entry.get("japanese", []):
            forms.add(jp.get("word") or "")
            forms.add(jp.get("reading") or "")
        if word in forms:
            return entry, True
    return (data[0], False) if data else (None, False)


def easiest_tag(jlpt_levels):
    """Из ["jlpt-n3","jlpt-n5"] вернуть тег самого лёгкого уровня: "jlpt::n5"."""
    levels = [t for t in jlpt_levels if t.startswith("jlpt-n")]
    if not levels:
        return None
    # самый лёгкий = наибольший номер N
    easiest = max(levels, key=lambda t: int(t.rsplit("n", 1)[1]))
    return "jlpt::" + easiest.split("-", 1)[1]  # "jlpt-n5" -> "jlpt::n5"


def lookup(word):
    entry, exact = pick(word, fetch(word))
    if entry is None:
        return {"word": word, "slug": None, "common": None,
                "jlpt": [], "jlpt_tag": None, "matched": "none"}
    jlpt = sorted(entry.get("jlpt", []))
    return {
        "word": word,
        "slug": entry.get("slug"),
        "common": bool(entry.get("is_common")),
        "jlpt": jlpt,
        "jlpt_tag": easiest_tag(jlpt),
        "matched": "exact" if exact else "first",
    }


def main(argv):
    words = argv
    if argv == ["-"]:
        words = [line.strip() for line in sys.stdin if line.strip()]
    result = []
    for word in words:
        result.append(lookup(word))
        time.sleep(0.3)  # вежливый троттлинг к jisho
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
