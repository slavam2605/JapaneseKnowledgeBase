# japaneseCards — карта папки

> **STATUS:** индекс/навигатор. Точка входа для человека и LLM. Читать первым.

Проект: пересборка Anki-колод для японского (фокус N5–N4 → позже N3) для двух
русскоязычных учащихся. Цель/аудитория и все общие соглашения — в
[knowledge/conventions.md](knowledge/conventions.md).

Файлы разложены **по роли**: `knowledge/` — стабильное знание (что правда), `data/` —
изменяемые рабочие данные (очереди входного материала), `tools/` — скрипты, `logs/` —
append-only журналы операций, `background/` — история. Грузи в контекст только
то, что нужно под задачу.

**Что уже сделано и что в очереди — в [STATUS.md](STATUS.md).** Читать, когда непонятно,
какой материал уже залит в Anki; обновлять после каждой партии карточек.

## `knowledge/` — нормативка, это закон, соблюдать

| Файл | Что это | Читать когда |
|---|---|---|
| [knowledge/conventions.md](knowledge/conventions.md) | **единый источник** общего: безопасность Anki, цель/аудитория, имена колод/типов, теги, синтаксис ввода, фуригана, словарь, механика записи `anki_add.py` | **всегда** перед любой записью в Anki |
| [knowledge/card-types.md](knowledge/card-types.md) | **деление на типы**: какие типы есть и по какой логике материал попадает в каждый (без деталей создания) | когда непонятно, каким типом учить материал |
| [knowledge/words-cards.md](knowledge/words-cards.md) | **источник правды** по типу «Слова»: поля, правила полей, теги уровня, HTML/JS/CSS | перед созданием/правкой карточек `AiGeneratedJapaneseWords` |
| [knowledge/kanji-cards.md](knowledge/kanji-cards.md) | **источник правды** по типу «Чтение кандзи»: поля, правила полей, HTML/CSS | перед созданием/правкой карточек `AiGeneratedJapaneseKanji` |
| [knowledge/grammar-cards.md](knowledge/grammar-cards.md) | **источник правды** по грамматическому типу: поля, алгоритмы `Hint`/`Meaning`, полный HTML/JS/CSS (Persistence + рандомизация cloze) | перед созданием/правкой карточек `AiGeneratedJapaneseGrammar` |
| [knowledge/mnn-catalog.md](knowledge/mnn-catalog.md) | **источник правды** по каталогу слов MNN: место (`data/reference/mnn/`), формат таблицы, нумерация уроков, правила извлечения | при извлечении слов из MNN или чтении каталога для карточек |

Процессы (как наполнять/разбирать/править/извлекать) — в общих для агентов скиллах в корневом
`.agents/skills/` репозитория (`japanese-cards`, `process-inbox`, `process-remarks`, `mnn-extract`,
`dedup-cards`). `.claude/skills/` содержит symlink'и на те же каталоги для Claude Code. Скиллы
ссылаются на `knowledge/`, не дублируют её.

## `data/` — рабочие данные, изменяемое

`inbox.md` — **точка входа** для нового материала: пользователь накидывает туда слова / кандзи /
грамматику / вопросы вперемешку, а скилл `process-inbox` раскладывает их по целевым файлам
(`words.md`, `kanji.md`, `grammar.md`) и отвечает на вопросы в `answers.md`.

| Файл | Что это |
|---|---|
| [data/inbox.md](data/inbox.md) | **entry-point**: неразобранный поток на распределение |
| [data/words.md](data/words.md) | бэклог слов для `新日本語::Слова` |
| [data/kanji.md](data/kanji.md) | бэклог чтений кандзи для `新日本語::Чтение кандзи` |
| [data/grammar.md](data/grammar.md) | бэклог грамматики для `新日本語::Грамматика` |
| [data/answers.md](data/answers.md) | ответы на языковые вопросы из `inbox.md` |
| [data/reference/existing_grammar_rating.md](data/reference/existing_grammar_rating.md) | статичная справка: оценка JLPT-уровней старой колоды грамматики |
| `data/reference/mnn/lessonNN.md`, `data/reference/mnn/extra/<тема>.md` | каталог слов из MNN (скилл `mnn-extract`); формат — [knowledge/mnn-catalog.md](knowledge/mnn-catalog.md) |

## `tools/` — скрипты (общие для скиллов)

Python-инструменты, вызываются по пути `python3 japaneseCards/tools/<script>.py`. Читают общие
ресурсы из `resources/` репозитория (те же, что и Kotlin-код); `dict_index.sqlite` — производный
артефакт, в `.gitignore`, пересобирается из ресурсов.

| Скрипт | Назначение |
|---|---|
| `dict_lookup.py` | оффлайн-лукап слов/кандзи (якорные факты против галлюцинаций) |
| `dict_build_index.py` | разовая сборка `dict_index.sqlite` из `resources/` |
| `anki_add.py` | создание карточек через AnkiConnect (canAdd → add → suspend → verify) |
| `fetch_remarks.py` | выгрузка заметок с непустым `Remarks` (для `process-remarks`) |
| `export_anki_notes.py`, `build_embeddings.py`, `search_similar.py` | эмбеддинг-индекс колод (поиск/дедуп); см. [tools/EMBEDDINGS.md](tools/EMBEDDINGS.md) |
| `dedup_scan.py` | read-only скан дублей архив↔новое → `data/removal_candidates{.json,_review.md}` (для `dedup-cards`) |
| `jisho_levels.py` | устаревший онлайн-фолбэк (jisho.org); обычно не нужен |

## `logs/` — журналы операций, append-only

Вывод автоматики/скиллов: дописывается в конец, никогда не «обрабатывается», нужен как аудит и
подстраховка. Не путать с очередями в `data/` (те убывают по мере обработки).

| Файл | Что это |
|---|---|
| [logs/remarks-log.md](logs/remarks-log.md) | лог исполненных правок из поля `Remarks` (скилл `process-remarks`) |

## `background/` — фон/история, read-only, только когда нужен «почему»

Тяжёлые файлы; не тащить в контекст без причины.

| Файл | Что это |
|---|---|
| [background/AnkiCardsIssues.md](background/AnkiCardsIssues.md) | изначальная постановка проблем в старых карточках |
| [background/JapaneseAnkiDeepResearch.md](background/JapaneseAnkiDeepResearch.md) | Deep Research от Gemini (большой) |
| [background/FollowUpDiscussion.md](background/FollowUpDiscussion.md) | обсуждение этого анализа |
| [background/ChatContext.md](background/ChatContext.md) | контекст исходного чата |

## Планируется

- `tools/anki_push` (card-types.md → Anki), `tools/anki_dump` (Anki → diff со спекой). Пока не
  реализованы. Создание партии карточек уже покрыто `tools/anki_add.py`.
