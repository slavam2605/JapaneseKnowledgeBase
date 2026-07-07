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

ANKI_URL = "http://localhost:8765"
DEFAULT_TAGS = ["ai_generated", "ai_generated::to_review"]

# Остаточная фуригана: ` 漢字[かな]` после рендера должна стать <ruby>. Если в готовом
# HTML остался литерал `[かな]` (кана в квадратных скобках) — фильтр фуриганы не сработал.
RESIDUAL_FURIGANA = re.compile(r"\[[ぁ-ゖァ-ヺー]+\]")


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
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"Ошибка входных данных: {e}\n")
        return 2
    print(f"Партия: {len(notes)} нот → {notes[0]['deckName']} / {notes[0]['modelName']}")

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
