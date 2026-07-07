#!/usr/bin/env python3
"""Собирает локальный словарный индекс (SQLite) из ресурсов репозитория.

Запускать ОДИН РАЗ (или после обновления ресурсов):
    python3 japaneseCards/tools/dict_build_index.py

Источники (всё уже лежит в resources/, скачивать ничего не надо):
  - JMdict         — чтения, значения (рус+англ), части речи, флаг "usually kana",
                     common по приоритетным кодам (news1/ichi1/spec/gai).
  - word_list_2.txt — кэш jisho: уровни JLPT (N5..N1) и common-флаг по (форма, чтение).
  - kanjidic2.xml   — официальный словарь кандзи (EDRDG): он/кун чтения + значения
                      (тот же источник, что у jisho.org). Скачать один раз:
                      curl -sSLo resources/kanjidic2.xml.gz \\
                          http://ftp.edrdg.org/pub/Nihongo/kanjidic2.xml.gz
                      gunzip -kf resources/kanjidic2.xml.gz

Результат — dict_index.sqlite рядом со скриптом. Это ПРОИЗВОДНЫЙ артефакт
(в .gitignore), пересобираемый из ресурсов; в репозиторий не коммитится.

Зависимости: только стандартная библиотека Python 3.
"""
import base64
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
# japaneseCards/tools -> корень репозитория на два уровня выше.
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
RESOURCES = os.path.join(REPO_ROOT, "resources")
DB_PATH = os.path.join(HERE, "dict_index.sqlite")

JMDICT = os.path.join(RESOURCES, "JMdict")
WORD_LIST = os.path.join(RESOURCES, "word_list_2.txt")
KANJIDIC = os.path.join(RESOURCES, "kanjidic2.xml")

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
# Коды приоритета, по которым jisho считает слово "common".
COMMON_PRI = {"news1", "ichi1", "ichi2", "spec1", "spec2", "gai1", "gai2"}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
#  Схема
# --------------------------------------------------------------------------- #
def create_schema(con):
    con.executescript(
        """
        DROP TABLE IF EXISTS word;
        DROP TABLE IF EXISTS form;
        DROP TABLE IF EXISTS level;
        DROP TABLE IF EXISTS kanji;

        CREATE TABLE word(
            id          INTEGER PRIMARY KEY,
            text        TEXT,    -- основная форма (первый keb, иначе первый reb)
            reading     TEXT,    -- основное чтение (первый reb)
            readings    TEXT,    -- json: все чтения
            meanings_ru TEXT,    -- json: русские значения (может быть пусто)
            meanings_en TEXT,    -- json: английские значения
            pos         TEXT,    -- json: части речи (описания JMdict)
            common      INTEGER, -- 1 если common по приоритетам JMdict
            uk          INTEGER  -- 1 если "usually written using kana alone"
        );
        -- Все поверхностные формы (kanji + kana) -> word.id, для лукапа по любой форме.
        CREATE TABLE form(surface TEXT, word_id INTEGER);

        -- Уровни из jisho-кэша, по (форма, чтение). Чтение может быть пустым.
        CREATE TABLE level(surface TEXT, reading TEXT, jlpt INTEGER, common INTEGER);

        CREATE TABLE kanji(
            char     TEXT PRIMARY KEY,
            on_yomi  TEXT,  -- json: он-чтения (катакана)
            kun_yomi TEXT,  -- json: кун-чтения (точка отделяет окуригану: した.がう)
            meanings TEXT,  -- json: англ. значения (референс)
            jlpt     INTEGER
        );
        """
    )


def create_indexes(con):
    con.executescript(
        """
        CREATE INDEX idx_form_surface ON form(surface);
        CREATE INDEX idx_level_surface ON level(surface);
        """
    )


# --------------------------------------------------------------------------- #
#  JMdict
# --------------------------------------------------------------------------- #
def build_jmdict(con):
    log("Парсинг JMdict (это самый долгий шаг)...")
    word_rows = []
    form_rows = []
    next_id = 0
    n = 0

    # iterparse держит в памяти только одну запись за раз.
    for event, entry in ET.iterparse(JMDICT, events=("end",)):
        if entry.tag != "entry":
            continue

        kebs, common = [], False
        for k in entry.findall("k_ele"):
            keb = k.findtext("keb")
            if keb:
                kebs.append(keb)
            for pri in k.findall("ke_pri"):
                if pri.text in COMMON_PRI:
                    common = True

        rebs = []
        for r in entry.findall("r_ele"):
            reb = r.findtext("reb")
            if reb:
                rebs.append(reb)
            for pri in r.findall("re_pri"):
                if pri.text in COMMON_PRI:
                    common = True

        pos, ru, en, uk = [], [], [], False
        for sense in entry.findall("sense"):
            for p in sense.findall("pos"):
                if p.text and p.text not in pos:
                    pos.append(p.text)
            for m in sense.findall("misc"):
                if m.text and "kana alone" in m.text:
                    uk = True
            for g in sense.findall("gloss"):
                if not g.text:
                    continue
                if g.attrib.get(XML_LANG) == "rus":
                    ru.append(g.text)
                elif XML_LANG not in g.attrib:  # default lang = eng
                    en.append(g.text)

        entry.clear()  # освобождаем память

        if not (kebs or rebs):
            continue

        wid = next_id
        next_id += 1
        text = kebs[0] if kebs else rebs[0]
        word_rows.append(
            (
                wid,
                text,
                rebs[0] if rebs else None,
                json.dumps(rebs, ensure_ascii=False),
                json.dumps(ru, ensure_ascii=False),
                json.dumps(en, ensure_ascii=False),
                json.dumps(pos, ensure_ascii=False),
                1 if common else 0,
                1 if uk else 0,
            )
        )
        for surface in set(kebs) | set(rebs):
            form_rows.append((surface, wid))

        n += 1
        if n % 50000 == 0:
            log(f"  обработано записей: {n}")

    con.executemany(
        "INSERT INTO word VALUES (?,?,?,?,?,?,?,?,?)", word_rows
    )
    con.executemany("INSERT INTO form VALUES (?,?)", form_rows)
    log(f"JMdict: {n} записей, {len(form_rows)} поверхностных форм.")


# --------------------------------------------------------------------------- #
#  word_list_2.txt (jisho-кэш: JLPT + common)
# --------------------------------------------------------------------------- #
def _b64(s):
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:
        return ""


def _reading_from(text, furi_field):
    """Восстановить чтение каной из text + поля furigana (как WordEntryImpl.getReading)."""
    segs = [_b64(x) for x in furi_field.split("|")]
    if len(segs) != len(text):
        return ""  # не сопоставилось — чтение не пишем
    out = []
    for ch, seg in zip(text, segs):
        out.append(ch if seg == "" else seg)
    return "".join(out)


def _jlpt_of(tags):
    for n in (5, 4, 3, 2, 1):  # самый лёгкий уровень
        if f"JLPT N{n}" in tags:
            return n
    return None


def build_levels(con):
    log("Парсинг word_list_2.txt (уровни JLPT + common)...")
    rows = []
    n = 0
    with open(WORD_LIST, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("<"):
                continue
            parts = line.split(":we:")
            if len(parts) < 4:
                continue
            text = _b64(parts[0])
            if not text:
                continue
            reading = _reading_from(text, parts[1])
            tags = {_b64(t) for t in parts[3].split("|") if t}
            jlpt = _jlpt_of(tags)
            common = 1 if "Common word" in tags else 0
            if jlpt is None and not common:
                continue  # нечего хранить
            rows.append((text, reading, jlpt, common))
            n += 1
            if n % 50000 == 0:
                log(f"  уровней собрано: {n}")
    con.executemany("INSERT INTO level VALUES (?,?,?,?)", rows)
    log(f"word_list_2.txt: {n} записей с уровнем/common.")


# --------------------------------------------------------------------------- #
#  kanji_info.json
# --------------------------------------------------------------------------- #
def build_kanji(con):
    log("Парсинг kanjidic2.xml (он/кун чтения + значения)...")
    rows = []
    for event, ch_el in ET.iterparse(KANJIDIC, events=("end",)):
        if ch_el.tag != "character":
            continue
        lit = ch_el.findtext("literal")
        if not lit:
            ch_el.clear()
            continue
        on, kun = [], []
        for rd in ch_el.findall(".//reading"):
            t = rd.attrib.get("r_type")
            if t == "ja_on" and rd.text:
                on.append(rd.text)
            elif t == "ja_kun" and rd.text:
                kun.append(rd.text)
        meanings = [
            m.text
            for m in ch_el.findall(".//meaning")
            if "m_lang" not in m.attrib and m.text  # без m_lang = английский
        ]
        jlpt = ch_el.findtext(".//misc/jlpt")
        rows.append(
            (
                lit,
                json.dumps(on, ensure_ascii=False),
                json.dumps(kun, ensure_ascii=False),
                json.dumps(meanings, ensure_ascii=False),
                int(jlpt) if jlpt else None,
            )
        )
        ch_el.clear()
    con.executemany("INSERT INTO kanji VALUES (?,?,?,?,?)", rows)
    log(f"kanjidic2.xml: {len(rows)} кандзи.")


# --------------------------------------------------------------------------- #
def main():
    for path in (JMDICT, WORD_LIST, KANJIDIC):
        if not os.path.exists(path):
            log(f"ОШИБКА: нет файла-ресурса {path}")
            sys.exit(1)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    try:
        create_schema(con)
        build_jmdict(con)
        build_levels(con)
        build_kanji(con)
        create_indexes(con)
        con.commit()
        con.execute("VACUUM")
    finally:
        con.close()
    size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
    log(f"Готово: {DB_PATH} ({size_mb:.1f} МБ)")


if __name__ == "__main__":
    main()
