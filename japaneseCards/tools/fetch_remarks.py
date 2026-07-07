#!/usr/bin/env python3
"""Выгрузка карточек с непустым полем `Remarks` через AnkiConnect.

Чисто механическая часть процесса правок: находит все заметки, у которых поле
`Remarks` не пустое, и печатает их в JSON на stdout. Интерпретацию и исполнение
правок делает скилл `process-remarks` (там нужен LLM), не этот скрипт.

Запуск (Anki должен быть открыт, аддон AnkiConnect слушает localhost:8765):
    python3 fetch_remarks.py            # JSON-массив заметок на stdout
    python3 fetch_remarks.py --pretty   # то же, человекочитаемо

Поиск: `Remarks:_*` — поле существует и непустое. Поле есть только в наших
note types (AiGenerated*), так что чужие карточки не попадут; для надёжности
дополнительно фильтруем по тегу `ai_generated`.
"""
import json
import sys
import urllib.request

ANKI_URL = "http://localhost:8765"
QUERY = "Remarks:_* tag:ai_generated"


def call(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(ANKI_URL, data=payload)
    resp = json.load(urllib.request.urlopen(req))
    if resp.get("error"):
        raise RuntimeError(f"{action}: {resp['error']}")
    return resp["result"]


def fetch():
    note_ids = call("findNotes", query=QUERY)
    if not note_ids:
        return []
    infos = call("notesInfo", notes=note_ids)

    # Колоду берём из первой карточки заметки (для переносов/контекста).
    card_ids = [c for info in infos for c in info.get("cards", [])]
    deck_by_card = {}
    if card_ids:
        for c in call("cardsInfo", cards=card_ids):
            deck_by_card[c["cardId"]] = c["deckName"]

    out = []
    for info in infos:
        fields = {name: f["value"] for name, f in info["fields"].items()}
        cards = info.get("cards", [])
        out.append({
            "noteId": info["noteId"],
            "modelName": info["modelName"],
            "deckName": deck_by_card.get(cards[0]) if cards else None,
            "cardIds": cards,
            "remark": fields.get("Remarks", ""),
            "fields": fields,
        })
    return out


def main():
    pretty = "--pretty" in sys.argv[1:]
    notes = fetch()
    if pretty:
        if not notes:
            print("Нет карточек с непустым Remarks.")
            return
        for n in notes:
            print(f"\n=== noteId {n['noteId']} | {n['modelName']} | {n['deckName']} ===")
            print(f"REMARK: {n['remark']}")
            for k, v in n["fields"].items():
                if k != "Remarks":
                    print(f"  {k}: {v}")
    else:
        json.dump(notes, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
