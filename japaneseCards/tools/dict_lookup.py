#!/usr/bin/env python3
"""Локальный словарный лукап для скилла japanese-cards (оффлайн, без сети).

Читает dict_index.sqlite (собирается dict_build_index.py). Если индекса нет —
подскажет, как его собрать.

Слова (якорные факты для генерации/проверки карточек):
    python3 dict_lookup.py 切符 たぶん 銀行員
    echo '切符\nたぶん' | python3 dict_lookup.py -

Кандзи (валидные он/кун чтения — для проверки колоды «Чтение кандзи»):
    python3 dict_lookup.py --kanji 退 結 集

Вывод — JSON-массив. Для слова:
    {query, found, reading, readings, meanings_ru, meanings_en, pos,
     common, uk, jlpt, jlpt_tag, matched}
где:
  - found      — нашлось ли слово в JMdict;
  - matched    — "exact" (форма точно есть среди поверхностных форм) | "none";
  - common     — common-флаг (jisho-кэш в приоритете, иначе приоритеты JMdict);
  - jlpt        — самый лёгкий уровень (5..1) или null;
  - jlpt_tag    — рекомендуемый тег "jlpt::nX" или null (как в старом jisho_levels.py).

Заменяет jisho_levels.py: те же поля common/jlpt/jlpt_tag/matched берутся
локально, без запросов к jisho.org.
"""
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "dict_index.sqlite")


def die_no_db():
    print(
        "ОШИБКА: нет dict_index.sqlite. Собери индекс один раз:\n"
        "    python3 japaneseCards/tools/dict_build_index.py",
        file=sys.stderr,
    )
    sys.exit(1)


def connect():
    if not os.path.exists(DB_PATH):
        die_no_db()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def lookup_word(con, query):
    rows = con.execute(
        """
        SELECT w.* FROM word w
        JOIN form f ON f.word_id = w.id
        WHERE f.surface = ?
        """,
        (query,),
    ).fetchall()

    # Уровни/common из jisho-кэша (по форме).
    lvls = con.execute(
        "SELECT jlpt, common FROM level WHERE surface = ?", (query,)
    ).fetchall()
    jlpt = None
    for r in lvls:
        if r["jlpt"] is not None and (jlpt is None or r["jlpt"] > jlpt):
            jlpt = r["jlpt"]  # самый лёгкий = наибольший N
    common_cache = any(r["common"] for r in lvls)

    if not rows:
        return {
            "query": query,
            "found": False,
            "reading": None,
            "readings": [],
            "meanings_ru": [],
            "meanings_en": [],
            "pos": [],
            "common": common_cache,
            "uk": False,
            "jlpt": jlpt,
            "jlpt_tag": f"jlpt::n{jlpt}" if jlpt else None,
            "matched": "none",
        }

    # Берём запись с самым богатым набором значений как основную.
    def richness(r):
        return len(json.loads(r["meanings_ru"])) + len(json.loads(r["meanings_en"]))

    main = max(rows, key=richness)
    readings, meanings_ru, meanings_en, pos = [], [], [], []
    for r in rows:  # объединяем чтения по всем омографам этой формы
        for x in json.loads(r["readings"]):
            if x not in readings:
                readings.append(x)
    meanings_ru = json.loads(main["meanings_ru"])
    meanings_en = json.loads(main["meanings_en"])
    pos = json.loads(main["pos"])
    common = common_cache or any(r["common"] for r in rows)
    uk = any(r["uk"] for r in rows)

    return {
        "query": query,
        "found": True,
        "reading": main["reading"],
        "readings": readings,
        "meanings_ru": meanings_ru,
        "meanings_en": meanings_en,
        "pos": pos,
        "common": bool(common),
        "uk": bool(uk),
        "jlpt": jlpt,
        "jlpt_tag": f"jlpt::n{jlpt}" if jlpt else None,
        "matched": "exact",
    }


def lookup_kanji(con, ch):
    r = con.execute(
        "SELECT on_yomi, kun_yomi, meanings, jlpt FROM kanji WHERE char = ?", (ch,)
    ).fetchone()
    if r is None:
        return {"kanji": ch, "found": False, "on_yomi": [], "kun_yomi": [],
                "meanings_en": [], "jlpt": None}
    return {
        "kanji": ch,
        "found": True,
        "on_yomi": json.loads(r["on_yomi"]),
        "kun_yomi": json.loads(r["kun_yomi"]),
        "meanings_en": json.loads(r["meanings"]),
        "jlpt": r["jlpt"],
    }


def main(argv):
    kanji_mode = False
    if argv and argv[0] == "--kanji":
        kanji_mode = True
        argv = argv[1:]

    if argv == ["-"]:
        items = [line.strip() for line in sys.stdin if line.strip()]
    else:
        items = argv

    con = connect()
    try:
        if kanji_mode:
            # Поддержать как отдельные кандзи, так и склеенную строку.
            chars = []
            for a in items:
                chars.extend(list(a))
            result = [lookup_kanji(con, c) for c in chars]
        else:
            result = [lookup_word(con, w) for w in items]
    finally:
        con.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
