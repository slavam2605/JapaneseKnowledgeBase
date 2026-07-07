# `AiGeneratedJapaneseGrammar` — карточки-паттерны (рандомизированный cloze)

> **STATUS:** источник правды по грамматическому типу — **поля, правила их заполнения, алгоритмы
> (Hint/Meaning), HTML + JS + CSS**. Совпадает с тем, что реально стоит в Anki. Менять шаблон/стили —
> сначала тут, потом в Anki. Чем этот тип отличается от других и что в него попадает (scope) —
> в [card-types.md](card-types.md) разд. 3; общие правила (безопасность, теги, suspend, фуригана,
> механика `anki_add.py`) — в [conventions.md](conventions.md).

Односторонняя карточка JP→RU с **рандомизацией предложения на каждом показе** и **рукописным
cloze** (свой JS вместо нативного `{{cloze:}}`, который рендерится до JS и не умеет рандомизировать).
На каждом показе JS выбирает случайный пример из `Expressions`, прячет целевую конструкцию `❰…❱` и
показывает в пропуске короткую RU-подсказку `【…】`.

**Scope коротко:** тип определяется механикой (cloze + рандомизация), а не тем, «грамматика» ли это
в учебниковом смысле. Сюда же — выбор частицы при слове (`友達[ともだち]に 会[あ]う` → `❰に❱`) и
продуктивные суффиксы (`〜すぎる`, `〜やすい/にくい`, `〜方[かた]`). Полное определение scope и граница
с отложенным типом словоформ — в [card-types.md](card-types.md) §3.

## Поля и правила заполнения

`Expressions` · `Grammar` · `Meaning` · `Hint` · `Notes` · `Remarks` (порядок в Anki; `Expressions` — sort field).

- **`Expressions`** — список примеров формата `JP ❰ответ❱ ||| RU`, разделённых тегом `<br>`.
  - **Разделитель — именно `<br>`, не перевод строки `\n`.** Фильтр фуриганы не считает `\n`
    разделителем (только пробел и `>`), поэтому при `\n` он склеивает хвост RU-перевода одной
    строки с кандзи следующей (`провалил экзамен.\n日本[にほん]` → ruby на «экзамен.\n日本»).
    `>` из `<br>` обрывает захват базы фуриганы — склейки нет. JS режет примеры по `<br>` и `\n`.
  - Целевая конструкция (то, что вспоминаем) обёрнута в маркер `❰…❱`. Несколько маркеров в одном
    примере допустимы (на лице прячутся все).
  - Фуригана — **только здесь**, bracket-нотацией ` 漢字[かな]` (правила пробелов — в conventions.md,
    раздел «Фуригана»; **пробел перед каждой кандзи-группой обязателен, в т.ч. после `❱`**, иначе
    `❰の❱机[つくえ]` растянет ruby поверх `❰の❱机`).
  - Разделитель JP/RU — ` ||| ` (три half-width пайпа в пробелах).
  - **Инлайн-хинт** (редко): если у пропуска свой смысл, отличный от общего `Meaning`, пишем
    `❰ответ｜хинт❱` через **full-width** `｜` (U+FF5C) — он не конфликтует с разделителем `|||`.
  - **Короткие примеры N5–N4**, я генерирую их сам; цель — естественный показательный случай, а не объём.
- **`Meaning`** — короткий RU-смысл конструкции; на лице вставляется **в пропуск** как `【…】`.
  Общий на грамматику (одна короткая подсказка, повторяется во всех примерах). Подробный алгоритм —
  ниже, «Поле `Meaning`».
- **`Hint`** — поле **разрешения неоднозначности** на лице, **под предложением** (НЕ «подсказка»).
  Часто **пустое**. Заполнять строго по алгоритму ниже, «Поле `Hint`».
- **`Grammar`** — JP-шаблон конструкции (`Vた＋が／けど`, `N₁のN₂`). Только на обороте. Рендерится через
  `{{furigana:Grammar}}`, поэтому **на каждую кандзи-группу обязательна фуригана** bracket-нотацией
  ` 漢字[かな]` (напр. `普通形[ふつうけい]`, `場所[ばしょ]`). Кана/латиница/символы (`Vた`, `の`, `＋`)
  проходят как есть. Проверять рендер `gpattern` через `cardsInfo` (должен быть `<ruby>`).
- **`Notes`** — развёрнутое пояснение нюанса. Только на обороте. Может быть пуст. Держать **коротким**
  (1–2 предложения). Рендерится через `{{furigana:Notes}}`, поэтому кандзи можно давать с фуриганой
  bracket-нотацией (` 漢字[かな]`), напр. `何時[なんじ]`; обычный текст проходит как есть.
- **`Remarks`** — служебное поле правок (см. [card-types.md](card-types.md)); скилл создания его не
  заполняет (обрабатывает `process-remarks`); нигде не рендерится.
- **Теги уровня JLPT/common НЕ ставить** (грамматика — не лексика). Только `ai_generated`
  (+ `ai_generated::to_review`).

## Поле `Meaning` — смысл в пропуск, а не описание грамматики

`Meaning` встаёт **в пропуск** на лице как `【…】` — это короткий RU-**смысл** конструкции
(`хоть и`, `о/про`, `дайте, пожалуйста`).

- **Нет лексического смысла → пустой ориентир `…`.** Если ответ — чистая грамматическая
  связка/частица без перевода (напр. `な` у な-прилагательных: `きれい❰な❱ 花`, или тематическая `は`),
  осмысленной RU-подсказки у пропуска нет. Тогда `Meaning` = одно многоточие `…` (пропуск
  отрисуется как `【…】` — просто «вставь недостающее»), а НЕ описание грамматики.
- **Никогда не описывай грамматику в `Meaning`.** ❌ `перед сущ.`, ❌ `な-прил.`, ❌ `соединяет N+N` —
  это та же ошибка, что спойлерить ответ в `Hint`. Описание/разбор — в `Notes`. Если не получается
  дать короткий **смысл** (а не описание) — ставь `…`.

## Поле `Hint` — разрешение неоднозначности

`Hint` **не «подсказка к ответу».** Его единственная задача — развести случаи, когда в пропуск по
смыслу подходит **несколько грамматически верных** ответов и из предложения нельзя угадать нужный.
**Часто поле пустое — это нормально и правильно** (когда контекст оставляет один вариант).

**Алгоритм заполнения (выполнять для каждой карточки):**
1. Зафиксируй ответ и его `Meaning` (RU-смысл, который встаёт в пропуск).
2. Выпиши грамматики-кандидаты, которые подставляются в **этот же** пропуск и дают **тот же**
   смысл (`Meaning`): близкие синонимы цели этого уровня — в т.ч. та же функция в другом регистре.
3. Для каждого кандидата проверь: «если вписать именно его в **это** предложение — будет
   грамматично и осмысленно?» Если нет — он **не** конкурент (так отвалилось `もの`: ×ミラーさんもの,
   тогда как のもの — да). Каждый элемент будущего «не X» обязан реально подставляться в пример.
4. Решение: конкурентов нет → `Hint` **пустой**; есть ≥1 → `Hint` разводит их (чем — ниже).
5. Самопроверка: «убрал бы я `Hint` — выбрал бы учащийся правильный ответ только из предложения
   и `Meaning`?» Если да → оставить пустым.

**Чем разводить** (всё, что выбирает нужный вариант, НЕ называя и не описывая ответ):
- **исключение конкурентов** через «не»: `не のに、けど`, `не おねがいします`;
- **различающий признак/особенность** нужной формы: `вежливая речь`, `разговорный краткий ответ`,
  `письменный стиль` (любой признак, отличающий цель от конкурентов).

**Запрещено:**
- называть/описывать целевую грамматику или повторять её смысл (смысл уже в `Meaning`, разбор —
  в `Notes`). ❌ `の связывает два существительных`; ❌ `место + です (опущено にいます)`.
- костыли вместо реальных альтернатив: `1 мора каны`, `после た-формы`.
- filler-вставки (`то — …`). Символ исключения — **«не»**, не `≠`.

**Калибровочные примеры** (цель → реальные конкуренты в этом предложении → итоговый `Hint`):

| Пример (пропуск ❰…❱) | Ответ | Реальные конкуренты | Hint |
|---|---|---|---|
| くるま❰の❱ 本です | の | нет (между двумя сущ. только の; な невозможно) | *(пусто)* |
| ミラーさん❰の❱です | の | нет (の однозначно; のもの лишь длиннее) | *(пусто)* |
| 〜❰をください❱ | をください | をおねがいします (оба верны) | `не おねがいします` |
| Vた❰が❱、… | が | のに, けど (все уступительные подходят) | `не のに、けど` |
| 会議室❰です❱ (где кто-то) | です | にいます／にあります (полная форма) | `не にいます／にあります (кратко)` |
| 部屋❰に❱ 机が あります | に | **нет** — で неграмотно с あります (существование), а で＋あります бывает только у событий (`公園で パーティーが あります`) | *(пусто)*; контраст に↔で — в `Notes` |

Последняя строка — **калибровка «ложного конкурента».** `не で` в этом примере был бы ошибкой: で не
подставляется в существование предмета (`ある／いる` требуют に), значит конкурентом не является и в
`Hint` не идёт. Разница «предмет→に / событие→で» — материал для `Notes`, а не для пропуска.

## Покрытие форм присоединения

Если конструкция присоединяется **несколькими формами с общим смыслом** (Vる／Aい／Nの＋うちに) —
примеры должны покрывать каждую форму, **минимум по одному**, а не повторять одну и ту же.
Варьирующаяся часть присоединения уходит **в** `❰…❱` (для Nの — `❰のうちに❱`, чтобы отрабатывалось
само の; для Vる／Aい — `❰うちに❱`). Иначе рандомизация генерализует лишь содержание предложения, а не
грамматическое присоединение.

- Форма с **другим смыслом** (Vない＋うちに = «до того как» против Vる＋うちに = «пока») — **отдельная
  карточка** со своим `Meaning` и своим FSRS-интервалом, а не пример здесь.
- **Естественность приоритетнее полноты покрытия:** если какая-то форма звучит редко/неуклюже на
  уровне N5–N4 — пропустить её, а не выжимать кривой пример.
- У конструкции с **одной** формой присоединения — как обычно, 2–3 примера.

## Несколько грамматических точек в одном предложении → отдельные карточки

Одно предложение часто несёт **несколько** самостоятельных грамматических точек, каждую из которых
стоит выучить. Не пытаться спрятать их одним пропуском или впихнуть в одну карточку — **заводить
отдельную карточку на каждую точку** (одна карточка = один отрабатываемый концепт). Честный
рандомизированный cloze «спрячь то одно, то другое» мы не умеем (JS прячет фиксированные `❰…❱`),
поэтому разнесение по карточкам — штатный механизм, а не костыль. Дубль материала в колоде —
**норма**: одно и то же предложение может стоять в нескольких карточках с разными пропусками.

- **Делить по грамматической точке, а не по токену.** Каждая получившаяся карточка — полноценная,
  по общим правилам: свой `Meaning`, свой `Hint`, свой `Grammar`, свои 2–3 примера.
- **Источник можно дублировать или менять.** Карточки могут опираться на одно и то же исходное
  предложение (одна прячет одну конструкцию, другая — другую) **или на разные предложения** — каждая
  подбирает примеры под свою точку, не оглядываясь на остальные.
- **Несколько `❰…❱` в одной карточке — только для ОДНОЙ точки.** Если конструкция состоит из
  разнесённых кусков с общим смыслом (`〜たり…たり`, парные `も…も`), все её куски прячем вместе в
  одном примере (несколько маркеров допустимы — см. «Поля», `Expressions`). Две **разные** точки в
  одном примере вместе НЕ прячем — это и есть повод для отдельной карточки.

**Воркфлоу:** глядя на предложение, выписать точки-кандидаты, отобрать достойные уровня, на каждую
завести карточку; в черновике показать их все разом.

**Пример.** `ベッドとテーブルの間に猫がいます。` («Между кроватью и столом — кошка») → две карточки:
1. **`AとBの間に`** — положение «между двумя ориентирами». Прячем чанк `の間に`:
   `ベッドとテーブル❰の 間[あいだ]に❱ 猫[ねこ]が います。` · `Meaning` = «между (А и Б)» · `と` показан как контекст.
2. **Перечислительное `と`** («A и B»). Прячем сам `と`:
   `ベッド❰と❱テーブルの 間[あいだ]に 猫[ねこ]が います。` · `Meaning` = «и» (без описания грамматики) ·
   `Hint` = «между чем-то и чем-то». В каркасе `AとBの間` форма `や` невозможна
   (`テーブルやベッドやの間` не говорят), поэтому `не や` было бы **ложным конкурентом** — хинт вместо
   этого подсказывает сам каркас «между…и…». Естественная форма — один `と` (`AとBの間`, не `AとBとの間`).

## Поведение

- **Лицо:** случайный пример; на месте каждого `❰…❱` — `【{{Meaning}}】` (или инлайн-хинт); под
  предложением — `Hint`; полный перевод свёрнут в `<details>` (раскрывается тапом).
- **Оборот:** **тот же** пример; `❰…❱` раскрыт (жирным, красным); `<hr>`; полный перевод (виден);
  `Grammar`; `Notes`.
- **FSRS** привязан к грамматике, а не к предложению (рандомизация на каждом показе) — сознательно,
  ради генерализации.

## Два технических камня

1. **Один и тот же случайный пример на лице и обороте.** Anki рендерит Front и Back отдельными
   проходами, JS на обороте запустился бы заново и выбрал другой пример. Решение — **Anki
   Persistence** (SimonLammer): на лице выбираем индекс и `Persistence.setItem`, на обороте
   `Persistence.getItem`. Работает на desktop / AnkiDroid / AnkiMobile. Если Persistence
   недоступен — оборот падает на индекс 0 (graceful fallback, рассинхрон только в этом редком случае).
2. **Фуригана vs разметка.** `{{furigana:Expressions}}` трогает только ` 漢字[かな]`; разделитель
   ` ||| ` и маркеры `❰…❱`, `【】` он не трогает (там нет `[]`). JS режет **уже готовый** HTML
   (regex по литералам `❰…❱`), `<ruby>` от фуриганы не ломается — кандзи-ответ в `❰…❱` тоже может
   нести фуригану и раскроется с ruby.

## Проверка после записи (специфика грамматики)

JS внутри карточки через AnkiConnect не исполняется, поэтому через `cardsInfo` проверяю
**отрендеренный `g-raw`**: фуригана применилась ко всем кандзи-группам, маркеры `❰…❱`, разделители
` ||| ` и `<br>` целы, нет склейки RU+кандзи. Отдельно: `<ruby>` не захватил `❰…❱` (база каждого
`<rt>` — ровно его кандзи, а не маркер слева); если захватил — не хватает пробела между `❱` и
кандзи-группой. Рандомизацию и совпадение примера на лице/обороте (Persistence) пользователь
проверяет глазами в Anki — это не вытаскивается из AnkiConnect.

---

## Front Template

```html
<div id="g-sentence" class="word"></div>
{{#Hint}}<div class="ghint">{{Hint}}</div>{{/Hint}}
<details class="gtr"><summary>перевод</summary><div id="g-trans"></div></details>

<div id="g-raw" hidden>{{furigana:Expressions}}</div>
<div id="g-meaning" hidden>{{Meaning}}</div>

<script>
// ---- Anki Persistence 0.7.x (github.com/SimonLammer/anki-persistence) ----
if (typeof(window.Persistence) === 'undefined') {
  var _persistenceKey = 'github.com/SimonLammer/anki-persistence/';
  var _defaultKey = '_default';
  window.Persistence_sessionStorage = function() {
    var isAvailable = false;
    try {
      if (typeof(window.sessionStorage) === 'object') {
        isAvailable = true;
        this.clear = function() { for (var i=0;i<sessionStorage.length;i++){var k=sessionStorage.key(i);if(k.indexOf(_persistenceKey)==0){sessionStorage.removeItem(k);i--;}} };
        this.setItem = function(key,value){ if(value==undefined){value=key;key=_defaultKey;} sessionStorage.setItem(_persistenceKey+key,JSON.stringify(value)); };
        this.getItem = function(key){ if(key==undefined){key=_defaultKey;} return JSON.parse(sessionStorage.getItem(_persistenceKey+key)); };
        this.removeItem = function(key){ if(key==undefined){key=_defaultKey;} sessionStorage.removeItem(_persistenceKey+key); };
      }
    } catch(err) {}
    this.isAvailable = function(){ return isAvailable; };
  };
  window.Persistence_windowKey = function(persistentKey) {
    var obj = window[persistentKey]; var isAvailable = false;
    if (typeof(obj) === 'object') {
      isAvailable = true;
      this.clear = function(){ obj[_persistenceKey] = {}; };
      this.setItem = function(key,value){ if(value==undefined){value=key;key=_defaultKey;} obj[_persistenceKey][key]=value; };
      this.getItem = function(key){ if(key==undefined){key=_defaultKey;} return obj[_persistenceKey][key]==undefined?null:obj[_persistenceKey][key]; };
      this.removeItem = function(key){ if(key==undefined){key=_defaultKey;} delete obj[_persistenceKey][key]; };
      if (obj[_persistenceKey] == undefined) { this.clear(); }
    }
    this.isAvailable = function(){ return isAvailable; };
  };
  window.Persistence = new Persistence_sessionStorage();
  if (!Persistence.isAvailable()) { window.Persistence = new Persistence_windowKey("py"); }
  if (!Persistence.isAvailable()) {
    var t = window.location.toString().indexOf('title');
    var c = window.location.toString().indexOf('main', t);
    if (t>0 && c>0 && (c-t)<10) { window.Persistence = new Persistence_windowKey("qt"); }
  }
}
// ---- end Persistence ----

(function(){
  function getExamples(){
    var raw = document.getElementById('g-raw'); if(!raw) return [];
    var parts = raw.innerHTML.split(/<br\s*\/?>|\n/), ex = [];
    for (var i=0;i<parts.length;i++){ var s = parts[i].trim(); if(s.length) ex.push(s); }
    return ex;
  }
  var ex = getExamples(), n = ex.length;
  if (!n) return;
  var idx = n > 1 ? Math.floor(Math.random()*n) : 0;
  if (typeof Persistence !== 'undefined' && Persistence.isAvailable()) Persistence.setItem('jpGrammarIdx', idx);

  var meaningEl = document.getElementById('g-meaning');
  var gapHint = meaningEl ? meaningEl.textContent.trim() : '';
  var seg = ex[idx].split(/\s*\|\|\|\s*/);
  var jp = (seg[0]||'').trim(), ru = (seg[1]||'').trim();
  jp = jp.replace(/❰([^❱]*)❱/g, function(m, body){
    var h = gapHint, i = body.indexOf('｜');
    if (i >= 0) h = body.slice(i+1).trim();
    return '<span class="gap">【'+h+'】</span>';
  });
  document.getElementById('g-sentence').innerHTML = jp;
  var t = document.getElementById('g-trans'); if(t) t.innerHTML = ru;
})();
</script>
```

## Back Template

```html
<div id="g-sentence" class="word"></div>
<hr>
<div id="g-trans" class="def"></div>
{{#Grammar}}<div class="gpattern">{{furigana:Grammar}}</div>{{/Grammar}}
{{#Notes}}<div class="note">{{furigana:Notes}}</div>{{/Notes}}

<div id="g-raw" hidden>{{furigana:Expressions}}</div>

<script>
// ---- Anki Persistence (тот же блок, что и на лице) ----
if (typeof(window.Persistence) === 'undefined') {
  var _persistenceKey = 'github.com/SimonLammer/anki-persistence/';
  var _defaultKey = '_default';
  window.Persistence_sessionStorage = function() {
    var isAvailable = false;
    try {
      if (typeof(window.sessionStorage) === 'object') {
        isAvailable = true;
        this.clear = function() { for (var i=0;i<sessionStorage.length;i++){var k=sessionStorage.key(i);if(k.indexOf(_persistenceKey)==0){sessionStorage.removeItem(k);i--;}} };
        this.setItem = function(key,value){ if(value==undefined){value=key;key=_defaultKey;} sessionStorage.setItem(_persistenceKey+key,JSON.stringify(value)); };
        this.getItem = function(key){ if(key==undefined){key=_defaultKey;} return JSON.parse(sessionStorage.getItem(_persistenceKey+key)); };
        this.removeItem = function(key){ if(key==undefined){key=_defaultKey;} sessionStorage.removeItem(_persistenceKey+key); };
      }
    } catch(err) {}
    this.isAvailable = function(){ return isAvailable; };
  };
  window.Persistence_windowKey = function(persistentKey) {
    var obj = window[persistentKey]; var isAvailable = false;
    if (typeof(obj) === 'object') {
      isAvailable = true;
      this.clear = function(){ obj[_persistenceKey] = {}; };
      this.setItem = function(key,value){ if(value==undefined){value=key;key=_defaultKey;} obj[_persistenceKey][key]=value; };
      this.getItem = function(key){ if(key==undefined){key=_defaultKey;} return obj[_persistenceKey][key]==undefined?null:obj[_persistenceKey][key]; };
      this.removeItem = function(key){ if(key==undefined){key=_defaultKey;} delete obj[_persistenceKey][key]; };
      if (obj[_persistenceKey] == undefined) { this.clear(); }
    }
    this.isAvailable = function(){ return isAvailable; };
  };
  window.Persistence = new Persistence_sessionStorage();
  if (!Persistence.isAvailable()) { window.Persistence = new Persistence_windowKey("py"); }
  if (!Persistence.isAvailable()) {
    var t = window.location.toString().indexOf('title');
    var c = window.location.toString().indexOf('main', t);
    if (t>0 && c>0 && (c-t)<10) { window.Persistence = new Persistence_windowKey("qt"); }
  }
}
// ---- end Persistence ----

(function(){
  function getExamples(){
    var raw = document.getElementById('g-raw'); if(!raw) return [];
    var parts = raw.innerHTML.split(/<br\s*\/?>|\n/), ex = [];
    for (var i=0;i<parts.length;i++){ var s = parts[i].trim(); if(s.length) ex.push(s); }
    return ex;
  }
  var ex = getExamples(), n = ex.length;
  if (!n) return;
  var idx = 0;
  if (typeof Persistence !== 'undefined' && Persistence.isAvailable()) {
    var v = Persistence.getItem('jpGrammarIdx');
    if (v !== null && v !== undefined && v < n) idx = v;
  }
  var seg = ex[idx].split(/\s*\|\|\|\s*/);
  var jp = (seg[0]||'').trim(), ru = (seg[1]||'').trim();
  jp = jp.replace(/❰([^❱]*)❱/g, function(m, body){
    var ans = body, i = body.indexOf('｜');
    if (i >= 0) ans = body.slice(0, i);
    return '<span class="gap ans">'+ans.trim()+'</span>';
  });
  document.getElementById('g-sentence').innerHTML = jp;
  var t = document.getElementById('g-trans'); if(t) t.innerHTML = ru;
})();
</script>
```

## CSS (Styling)

```css
.card { font-family: -apple-system, "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif; font-size: 22px; text-align: center; color: #222; background: #fff; }
.word { font-size: 24px; margin: 14px 0; line-height: 1.7; }
.gap { color: #2980b9; }
.gap.ans { font-weight: bold; color: #c0392b; }
.ghint { font-size: 18px; color: #c0392b; margin: 12px 0; }
.gtr { margin-top: 14px; font-size: 18px; color: #888; }
.gtr summary { cursor: pointer; color: #2980b9; list-style: none; }
.def { font-size: 20px; margin: 10px 0; }
.gpattern { font-size: 20px; color: #16a085; font-weight: bold; margin: 10px 0; }
.note { font-size: 18px; color: #888; font-style: italic; margin-top: 10px; }
hr { border: none; border-top: 1px solid #ccc; margin: 12px 0; }
ruby rt { font-size: 0.5em; color: #888; }
```

## Обязательная проверка субагентом перед записью

Грамматические карточки сложнее остальных (рукописный cloze, поле `Hint`, естественность примеров),
поэтому **перед записью в Anki их проверяет отдельный субагент-ревьюер**. Это обязательный gate
именно для типа «Грамматика» (для слов/кандзи не требуется). Порядок:

1. **Черновик, не Anki.** Подготовить карточки как данные (`batch.json` или таблица-черновик),
   **пока не заливать**.
2. **Запустить субагент-ревьюер** — свежий, **read-only** (он НЕ пишет в Anki, не вызывает
   `anki_add.py`). Дать ему: пути к правилам (`japaneseCards/knowledge/grammar-cards.md` +
   `conventions.md`, раздел «Фуригана») и сам черновик карточек. Задача — **адверсариально**
   проверить каждую карточку против всех правил ниже и вернуть структурированный список замечаний.
   Установка субагенту: искать проблемы, а не одобрять; при сомнении — отмечать.
3. **Исправить замечания.** Если есть блокирующие — поправить черновик и при существенных правках
   прогнать ревью ещё раз, пока блокеров не останется.
4. **Только после этого** — запись через `anki_add.py` (suspended + `ai_generated::to_review`).
5. Пользователь отсматривает карточки в Anki сам: снимает `suspend` и `ai_generated::to_review`.

**Что субагент обязан проверить (по каждой карточке):**
- **`Hint`** — не спойлерит и не описывает целевую грамматику; перечисляет только **реальных**
  конкурентов (каждый «не X» реально подставляется в это предложение и остаётся грамматичным); если
  конкурентов нет — поле пустое. Нет ложных конкурентов (тип ошибки `не で` при существовании). Прогон
  по алгоритму «Поле `Hint`», включая самопроверку шага 5.
- **`Meaning`** — короткий **смысл** в пропуск, а не описание грамматики; у связки без лексического
  смысла → `…`.
- **`Expressions`** — примеры естественные и уровня N5–N4; целевая конструкция обёрнута в `❰…❱`;
  если у грамматики несколько форм присоединения с общим смыслом — покрыта каждая; форма с **другим**
  смыслом не смешана в одну карточку; ответ в пропуске однозначен (или разведён через `Hint`).
- **Фуригана и разметка** — bracket-нотация, пробел перед каждой кандзи-группой (в т.ч. после `❱`);
  разделители `<br>` (не `\n`) и ` ||| ` на местах; `Grammar` несёт фуригану на всех кандзи-группах.
- **`Notes`** — короткий (1–2 предложения), не выполняет роль спойлера-Hint; теги уровня НЕ проставлены.

**Вывод субагента** — по каждой карточке: вердикт (ок / есть замечания) и конкретные находки
(поле · в чём нарушение · как поправить).

## Чек-лист на партию грамматики

- [ ] Короткие примеры N5–N4, целевая часть в `❰…❱`. Если у грамматики несколько форм присоединения
      с общим смыслом — по одному примеру на каждую (варьирующаяся часть в `❰…❱`); форма с другим
      смыслом — отдельная карточка. Одна форма → 2–3 примера.
- [ ] `Expressions`: примеры разделены `<br>`, фуригана bracket-нотацией, разделитель ` ||| `,
      пробел перед каждой кандзи-группой (в т.ч. после `❱`).
- [ ] `Meaning` — короткий RU-**смысл** в пропуск (не описание грамматики!); у связки без смысла → `…`.
- [ ] `Hint` проверен по алгоритму (нет реальных конкурентов в предложении → пусто; есть → разведены
      через «не» / признак, без спойлера и без ложных конкурентов).
- [ ] `Grammar` задан; все кандзи-группы в нём с фуриганой; `Notes` — если нужен разбор (коротко).
- [ ] Теги уровня НЕ проставлены; есть `ai_generated` + `ai_generated::to_review`.
- [ ] **Черновик прошёл проверку субагентом-ревьюером** (до записи в Anki); блокирующие замечания
      исправлены — см. «Обязательная проверка субагентом перед записью».
- [ ] Карточки заморожены (`suspend`); `g-raw` проверен через `cardsInfo` (фуригана + маркеры целы).

## Пример записи

| Expressions | Grammar | Meaning | Hint | Notes | Remarks |
|---|---|---|---|---|---|
| `たくさん 勉強[べんきょう]した❰が❱、 試験[しけん]に 落[お]ちた。 ||| Хотя много учился, провалил экзамен.<br>日本[にほん]へ 行[い]った❰が❱、 何[なに]も 買[か]わなかった。 ||| Съездил в Японию, но ничего не купил.` | Vた＋が | хоть и | не のに、けど | Мягкое противопоставление, как «но/хотя». | |

(`<br>` в поле `Expressions` — реальный разделитель примеров, а не оформление таблицы.)
