package server.pages

import dict.WordEntry
import io.ktor.server.application.ApplicationCall
import kotlinx.html.*
import server.kanjiPerDay
import utils.*
import utils.AnkiDataManager.deckName
import utils.KanjiLists.getJlptKanji
import kotlin.math.ceil
import kotlin.math.roundToInt

class LearnStatsPage(val dataset: Map<Char, List<WordEntry>>) : PageBuilderBase("/stats") {
    private var currentMode = "kanji"

    private fun isLearned(kanji: Char) =
        when (currentMode) {
            "kanji" -> "$kanji" in AnkiDataManager.kanjiDeck.keys
            "words" -> AnkiDataManager.kanjiWordsDeck.any { it.kanji.contains(kanji) }
            else -> error("Unknown mode: $currentMode")
        }

    override fun HEAD.buildHead() {
        script(src = "/collapsible.js") {}
        link("/tooltip.css", "stylesheet", "text/css")
        link("/learn_stats.css", "stylesheet", "text/css")
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        currentMode = call.parameters["mode"] ?: "kanji"
        val currentDeckName: String
        val otherDeckName: String
        val otherMode: String
        if (currentMode == "kanji") {
            currentDeckName = AnkiDataManager.KANJI_DECK.deckName()
            otherDeckName = AnkiDataManager.KANJI_WORDS_DECK.deckName()
            otherMode = "words"
        } else {
            currentDeckName = AnkiDataManager.KANJI_WORDS_DECK.deckName()
            otherDeckName = AnkiDataManager.KANJI_DECK.deckName()
            otherMode = "kanji"
        }

        div("head-block") {
            div {
                +"Процент использования кандзи в колоде $currentDeckName"
            }
            div {
                a("/stats?mode=$otherMode") {
                    +"Переключить на колоду $otherDeckName"
                }
            }
        }
        div {
            div("stat-card") {
                jlptKanjiStats()
            }
            div("stat-card") {
                jouyouKanjiStats()
            }
        }
    }

    private fun FlowContent.progressBar(value: Int, tooltipText: String? = null, isCollapsible: Boolean = false) {
        val tooltipClass = if (tooltipText != null) " tooltip" else ""
        val collapsibleClass = if (isCollapsible) " collapsible" else ""
        div("progress-bar-container$tooltipClass$collapsibleClass") {
            style = "margin-left: 0;"
            div("progress-bar-bar") {
                style = "width:$value%"
                +"$value%"
            }
            tooltipText?.let { text ->
                span("tooltiptext") {
                    +text
                }
            }
        }
    }

    private fun estimateKanjiDaysTooltip(left: Int): String {
        return if (left <= 0) {
            "Готово!"
        } else {
            val leftDays = ceil(left.toDouble() / kanjiPerDay).roundToInt()
            "Осталось ${convertDaysToString(leftDays)}"
        }
    }

    private fun FlowContent.kanjiStatsBlock(vararg entries: Pair<List<Char>, String>) {
        for ((kanjiList, name) in entries) {
            var learned = 0
            val total = kanjiList.size
            val missingKanji = mutableListOf<Char>()
            for (kanji in kanjiList) {
                if (isLearned(kanji)) {
                    learned++
                } else {
                    missingKanji.add(kanji)
                }
            }
            val ratio = (learned.toDouble() / total * 100).roundToInt()
            div {
                +"$name: $learned из $total"
                progressBar(ratio, estimateKanjiDaysTooltip(total - learned), true)
                div(classes = "content") {
                    style = "padding-left: 0;"
                    missingKanji.forEach {
                        a("/kanji?c=$it", classes = "kanji-link") { +"$it" }
                    }
                }
            }
        }
    }

    private fun FlowContent.jlptKanjiStats() {
        kanjiStatsBlock(
            getJlptKanji(5) to "Кандзи JLPT N5",
            getJlptKanji(4) to "Кандзи JLPT N4",
            getJlptKanji(3) to "Кандзи JLPT N3",
            getJlptKanji(2) to "Кандзи JLPT N2",
            getJlptKanji(1) to "Кандзи JLPT N1"
        )
    }

    private fun FlowContent.jouyouKanjiStats() {
        kanjiStatsBlock(
            KanjiLists.grade1 to "1 класс",
            KanjiLists.grade2 to "2 класс",
            KanjiLists.grade3 to "3 класс",
            KanjiLists.grade4 to "4 класс",
            KanjiLists.grade5 to "5 класс",
            KanjiLists.grade6 to "6 класс",
            KanjiLists.secondarySchool to "7-12 классы",
            KanjiLists.additions to "Дополнения"
        )
    }
}