package server.pages

import TxtWordsListProcessor
import dict.WordEntry
import io.ktor.application.*
import kotlinx.html.*
import org.jsoup.nodes.Element
import server.KanjiVG
import server.kanjiPerDay
import server.notLearnedKanjiList
import utils.*
import java.io.File

class KanjiIndexPage(
    val dataset: Map<Char, List<WordEntry>>,
    val kanjiVG: KanjiVG
) : PageBuilderBase("/") {
    private val allN45Words = TxtWordsListProcessor(resolveResource("jlpt_n5+n4_words.txt")).readSimpleList()
    private val missingWords = TxtWordsListProcessor(resolveResource(txtWordsFile)).readSimpleList()
    private val deckWords = TxtWordsListProcessor(File(exportedFilePath)).readExportedList() + allN45Words

    override fun HEAD.buildHead() {
        link("/kanji_index.css", "stylesheet", "text/css")
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        if (call.parameters["group_by_radical"] != null) {
            buildGroupedByRadicalPage()
        } else {
            buildNormalPage()
        }
    }

    private fun BODY.buildGroupedByRadicalPage() {
        val allKanji = dataset.keys
        val kanjiByRadical = mutableMapOf<String?, MutableList<Char>>()

        for (kanji in allKanji) {
            val element = kanjiVG.getElementForKanji(kanji)
            val radical = element.getKanjiRadical()
            kanjiByRadical.getOrPut(radical) { mutableListOf() }.add(kanji)
        }

        val sortedMap = kanjiByRadical.toList().sortedBy { (_, value) -> -value.size }
        for ((radical, kanjiList) in sortedMap) {
            if (radical == null)
                continue

            separator("Ключ $radical")
            kanjiList.sortBy { "$it" != radical }
            for (kanji in kanjiList) {
                kanjiIndexLink("$kanji")
            }
        }

        if (null in kanjiByRadical) {
            separator("Кандзи без ключа")
            for (kanji in kanjiByRadical[null]!!) {
                kanjiIndexLink("$kanji")
            }
        }
    }

    private fun Element.getKanjiRadical(): String? {
        val radicalValue = attr("kvg:radical")
        if (radicalValue == "general" || radicalValue == "tradit")
            return attr("kvg:element")

        return children().asSequence()
            .mapNotNull { it.getKanjiRadical() }
            .firstOrNull()
    }

    private fun BODY.buildNormalPage() {
        val learnedKanji = dataset.keys.filter { it !in notLearnedKanjiList }
        val restKanji = dataset.keys.filter { it !in learnedKanji }
        val todayKanji = restKanji.take(kanjiPerDay)
        val futureKanji = restKanji.drop(kanjiPerDay)

        separator("Изученные кандзи")
        for (kanji in learnedKanji) {
            when (kanji.hasWordsToLearn()) {
                0 -> kanjiIndexLink("$kanji")
                1 -> kanjiIndexLink("$kanji", "highlight")
                2 -> kanjiIndexLink("$kanji", "hot_highlight")
            }
        }

        separator("Кандзи на сегодня") { id = "main" }
        for (kanji in todayKanji) {
            kanjiIndexLink("$kanji", "toLearn")
        }

        separator("Будущие кандзи")
        for (kanji in futureKanji) {
            kanjiIndexLink("$kanji", "notLearned")
        }
    }

    private fun FlowContent.separator(text: String, block: DIV.() -> Unit = {}) {
        div("section_separator") {
            block()
            +text
        }
    }

    private fun Char.hasWordsToLearn(): Int {
        val info = getReadingInfoForKanji(this, dataset)
        val words = info.specialsWords + info.commonReadings.flatMap { when (it) {
            is ReadingInfo.SingleReading -> it.words
            is ReadingInfo.ReadingCollection -> (listOf(it.mainReading) + it.variations).flatMap { it.words }
        } }

        val hasWordsToLearn = words.asSequence()
            .filter { it.getJLPTLevel() == 3 }
            .filter { deckWords.all { w -> !w.sameWord(it) } || missingWords.any { w -> w.sameWord(it) } }
            .any()

        fun ReadingInfo.allWords() = when (this) {
            is ReadingInfo.SingleReading -> words
            is ReadingInfo.ReadingCollection -> mainReading.words + variations.flatMap { it.words }
        }
        val hasNoWordsLearned = info.commonReadings.all {
            !it.allWords().any { w -> (w.getJLPTLevel() ?: 0) >= 3 } ||
                    it.allWords().all { itit -> deckWords.all { w -> !w.sameWord(itit) } || missingWords.any { w -> w.sameWord(itit) } }
        } && info.commonReadings.any { it.allWords().any { w -> (w.getJLPTLevel() ?: 0) >= 3 } }

        return (if (hasWordsToLearn) 1 else 0) + (if (hasNoWordsLearned) 1 else 0)
    }

    private fun FlowContent.kanjiIndexLink(kanji: String, vararg classes: String) {
        val classesString = classes.joinToString(separator = "") { " $it" }
        a("/kanji?c=$kanji", classes = "index_kanji$classesString") {
            +kanji
        }
    }
}