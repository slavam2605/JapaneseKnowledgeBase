#!/usr/bin/env python3
"""Создание карточек Anki через AnkiConnect для скилла japanese-cards.

Вся механика создания (раздел «Механика создания» в SKILL.md) зашита здесь, чтобы
не писать каждый раз одноразовый скрипт. На вход — JSON-файл с *данными* карточек;
скрипт сам делает безопасную последовательность:

  version → canAddNotesWithErrorDetail → addNotes → suspend → cardsInfo (проверка рендера)

Использование:
    python3 anki_add.py notes.json              # создать (canAdd → add → suspend → verify)
    python3 anki_add.py notes.json --dry-run     # только canAddNotes (превью, ничего не пишет)
    cat notes.json | python3 anki_add.py -        # вход со stdin

Формат входного JSON — объект с дефолтами на партию:
    {
      "deck":  "新日本語::Грамматика",        # колода (обязательно)
      "model": "AiGeneratedJapaneseGrammar",  # note type (обязательно)
      "tags":  ["ai_generated", "ai_generated::to_review"],  # опц., это и есть дефолт
      "suspend": true,                          # опц., по умолчанию true (заморозить)
      "counter_reading_reviews": {              # только после обсуждения неоднозначности
        "七年": {"kana": "ななねん", "reason": "пользователь выбрал частотный вариант"}
      },
      "notes": [
        { "Expressions": "...", "Grammar": "...", "Meaning": "..." },   # только непустые поля
        ...
      ]
    }
Недостающие поля модели дополняются пустой строкой автоматически — в JSON
достаточно перечислить только заполняемые поля.

Альтернативно `notes` может быть массивом полноценных нот
(`{deckName, modelName, fields, tags}`) — тогда deck/model/tags берутся из них.

Безопасность (см. CLAUDE.md проекта): скрипт создаёт ТОЛЬКО новые заметки с тегом
`ai_generated`. Он не трогает чужие заметки, ничего не обновляет и не удаляет.
Если `canAddNotes` ругается (пустое первое поле / дубликат) — НЕ добавляет ничего.

Вывод — человекочитаемый отчёт + финальная строка `RESULT: {json}` для разбора.
Код возврата: 0 — успех; 1 — отказ canAdd/ошибка AnkiConnect; 2 — проблема входа/связи.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

import counter_readings

ANKI_URL = "http://localhost:8765"
DEFAULT_TAGS = ["ai_generated", "ai_generated::to_review"]
KANJI_MODEL = "AiGeneratedJapaneseKanji"
COUNTER_CATALOG_PATH = Path(__file__).with_name("counter_reading_catalog.json")

# Остаточная фуригана: ` 漢字[かな]` после рендера должна стать <ruby>. Если в готовом
# HTML остался литерал `[かな]` (кана в квадратных скобках) — фильтр фуриганы не сработал.
RESIDUAL_FURIGANA = re.compile(r"\[[ぁ-ゖァ-ヺー]+\]")


def load_counter_catalog():
    with COUNTER_CATALOG_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def split_numeric_expression(surface, numeric_characters):
    """Return (numeric prefix, remainder), or None for an ordinary expression."""
    index = 0
    while index < len(surface) and surface[index] in numeric_characters:
        index += 1
    if index == 0 or index == len(surface):
        return None
    return surface[:index], surface[index:]


def is_counter_expression(surface, lookup_result, catalog):
    """Recognize counters through UniDic POS, with a small lexicalized exception list."""
    split = split_numeric_expression(surface, catalog["numeric_characters"])
    if split is None:
        return False

    _, suffix = split
    if suffix in catalog["counter_suffix_exceptions"]:
        return True

    unidic = lookup_result.get("sources", {}).get("unidic") or {}
    return any(
        "助数詞" in node.get("pos", "")
        for node in unidic.get("nodes", [])
    )


def normalized_reading_key(reading, phoneme_key=counter_readings.reading_phonemes):
    reading = counter_readings.katakana_to_hiragana(reading.strip())
    return phoneme_key(reading)


def validate_counter_readings(
    notes,
    reviews=None,
    lookup=counter_readings.lookup,
    phoneme_key=counter_readings.reading_phonemes,
    catalog=None,
):
    """Validate counter cards without touching Anki; return checked surface/reading pairs.

    ``reviews`` is an explicit audit marker for cases already discussed with the user:
    ``{surface: {"kana": ..., "reason": ...}}``. It never bypasses missing evidence or a
    reading absent from the plausible candidates.
    """
    reviews = reviews or {}
    catalog = catalog or load_counter_catalog()
    checked = []

    for index, note in enumerate(notes):
        if note.get("modelName") != KANJI_MODEL:
            continue
        fields = note.get("fields", {})
        surface = fields.get("Kanji", "").strip()
        kana = fields.get("Kana", "").strip()
        if split_numeric_expression(surface, catalog["numeric_characters"]) is None:
            continue

        result = lookup(surface)
        if not result.get("complete"):
            errors = result.get("errors") or {"lookup": "unknown incomplete result"}
            detail = "; ".join(f"{source}: {error}" for source, error in errors.items())
            raise ValueError(
                f"Счётное чтение {surface!r} нельзя проверить полностью: {detail}. "
                "Используйте japaneseCards/.venv/bin/python и собранные локальные индексы."
            )
        counter_expression = is_counter_expression(surface, result, catalog)

        plausible = [candidate for candidate in result["candidates"] if candidate["plausible"]]
        plausible_keys = {
            normalized_reading_key(spelling, phoneme_key)
            for candidate in plausible
            for spelling in candidate.get("spellings", [candidate["reading"]])
        }
        supplied_key = normalized_reading_key(kana, phoneme_key)
        if supplied_key not in plausible_keys:
            readings = ", ".join(candidate["reading"] for candidate in plausible) or "нет"
            raise ValueError(
                f"Неверное или неподтверждённое Kana для {surface!r} (нота {index}): "
                f"{kana!r}; допустимые подтверждённые кандидаты: {readings}."
            )

        if result.get("needs_review"):
            review = reviews.get(surface)
            if not isinstance(review, dict):
                raise ValueError(
                    f"Чтение {surface!r} неоднозначно и требует обсуждения с пользователем. "
                    "После решения добавьте counter_reading_reviews с kana и reason."
                )
            reviewed_kana = str(review.get("kana", "")).strip()
            reason = str(review.get("reason", "")).strip()
            if not reviewed_kana or not reason:
                raise ValueError(
                    f"counter_reading_reviews[{surface!r}] должен содержать непустые kana и reason."
                )
            if normalized_reading_key(reviewed_kana, phoneme_key) != supplied_key:
                raise ValueError(
                    f"Согласованное kana для {surface!r} ({reviewed_kana!r}) "
                    f"не совпадает с полем Kana ({kana!r})."
                )

        checked.append(
            {
                "surface": surface,
                "kana": kana,
                "counter": counter_expression,
                "reviewed": result["needs_review"],
            }
        )

    return checked


def call(action, **params):
    """Один вызов AnkiConnect. Бросает RuntimeError на error в ответе."""
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(ANKI_URL, data=payload,
                                 headers={"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req))
    if resp.get("error"):
        raise RuntimeError(f"AnkiConnect '{action}': {resp['error']}")
    return resp["result"]


def load_spec(path):
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    return json.loads(raw)


def build_notes(spec):
    """Нормализует вход к списку нот AnkiConnect (deckName/modelName/fields/tags)."""
    notes_in = spec["notes"]
    # Вариант 2: уже полноценные ноты.
    if notes_in and all("fields" in n for n in notes_in):
        return [dict(n) for n in notes_in]
    # Вариант 1: партия с общими deck/model/tags, в notes — только поля.
    deck = spec["deck"]
    model = spec["model"]
    tags = spec.get("tags", DEFAULT_TAGS)
    # Область проверки дубликатов: по умолчанию ТОЛЬКО целевая колода + этот note type
    # (checkAllModels=false). Иначе AnkiConnect сверяет по всей коллекции и ловит ложные
    # «дубликаты» из старых колод с другими типами карточек. Переопределяется spec["options"].
    options = spec.get("options", {
        "allowDuplicate": False,
        "duplicateScope": "deck",
        "duplicateScopeOptions": {
            "deckName": deck,
            "checkChildren": False,
            "checkAllModels": False,
        },
    })
    field_names = call("modelFieldNames", modelName=model)
    notes = []
    for fields in notes_in:
        unknown = set(fields) - set(field_names)
        if unknown:
            raise ValueError(f"Неизвестные поля для {model}: {sorted(unknown)}")
        full = {name: fields.get(name, "") for name in field_names}
        notes.append({"deckName": deck, "modelName": model, "fields": full,
                      "tags": list(tags), "options": options})
    return notes


def check_can_add(notes):
    res = call("canAddNotesWithErrorDetail", notes=notes)
    bad = [(i, r) for i, r in enumerate(res) if not r.get("canAdd")]
    for i, r in bad:
        sys.stderr.write(f"  [нота {i}] canAdd=false: {r.get('error')}\n")
    return not bad


def verify(note_ids):
    """findCards по nid → suspend-флаг + остаточная фуригана в рендере. Возвращает отчёт."""
    nid_query = "nid:" + ",".join(str(i) for i in note_ids)
    card_ids = call("findCards", query=nid_query)
    info = call("cardsInfo", cards=card_ids)
    cards = []
    for c in info:
        rendered = c["question"] + "\n" + c["answer"]
        residual = RESIDUAL_FURIGANA.findall(rendered)
        cards.append({
            "cardId": c["cardId"],
            "suspended": c["queue"] == -1,
            "ruby": c["question"].count("<ruby>") + c["answer"].count("<ruby>"),
            "residual_furigana": residual,
        })
    return {"card_ids": card_ids, "cards": cards}


def main():
    args = [a for a in sys.argv[1:]]
    dry_run = "--dry-run" in args
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        sys.stderr.write(__doc__)
        return 2

    try:
        call("version")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Нет связи с AnkiConnect ({ANKI_URL}). Anki запущен? {e}\n")
        return 2

    try:
        spec = load_spec(paths[0])
        notes = build_notes(spec)
        counter_checks = validate_counter_readings(
            notes, reviews=spec.get("counter_reading_reviews")
        )
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"Ошибка входных данных: {e}\n")
        return 2
    print(f"Партия: {len(notes)} нот → {notes[0]['deckName']} / {notes[0]['modelName']}")
    if counter_checks:
        reviewed = sum(item["reviewed"] for item in counter_checks)
        print(
            f"Проверка числовых/счётных чтений: {len(counter_checks)} OK "
            f"(после обсуждения: {reviewed})"
        )

    if not check_can_add(notes):
        sys.stderr.write("canAddNotes не пройден — ничего не создано.\n")
        return 1
    print("canAddNotes: OK")

    if dry_run:
        print("RESULT: " + json.dumps({"dry_run": True, "would_add": len(notes)}, ensure_ascii=False))
        return 0

    note_ids = call("addNotes", notes=notes)
    if any(n is None for n in note_ids):
        sys.stderr.write(f"addNotes вернул null для части нот: {note_ids}\n")
        return 1
    print(f"addNotes: создано {len(note_ids)} нот")

    suspended_ok = True
    report = verify(note_ids)
    if spec.get("suspend", True):
        call("suspend", cards=report["card_ids"])
        report = verify(note_ids)  # перечитать состояние после suspend
        suspended_ok = all(c["suspended"] for c in report["cards"])
        print(f"suspend: {len(report['card_ids'])} карт заморожены (is:suspended={suspended_ok})")

    residual = [c for c in report["cards"] if c["residual_furigana"]]
    if residual:
        sys.stderr.write("⚠ Остаточная фуригана (фильтр не применился) в картах:\n")
        for c in residual:
            sys.stderr.write(f"    card {c['cardId']}: {c['residual_furigana']}\n")

    print(f"Проверка рендера: {len(report['cards'])} карт, "
          f"ruby-групп всего {sum(c['ruby'] for c in report['cards'])}, "
          f"остаточная фуригана {'НЕТ' if not residual else 'ЕСТЬ ⚠'}")
    print("RESULT: " + json.dumps({
        "note_ids": note_ids,
        "card_ids": report["card_ids"],
        "suspended_ok": suspended_ok,
        "residual_furigana": bool(residual),
    }, ensure_ascii=False))
    return 0 if (suspended_ok and not residual) else 1


if __name__ == "__main__":
    sys.exit(main())
