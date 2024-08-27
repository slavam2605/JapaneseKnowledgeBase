package server.pages

import TxtWordsListProcessor
import dict.AllWordsList
import dict.WordEntry
import io.ktor.server.application.ApplicationCall
import kotlinx.html.*
import org.jsoup.nodes.Element
import server.KanjiVG
import server.wordEntry
import utils.*
import java.io.File

class KanjiDetailsPage(
    val dataset: Map<Char, List<WordEntry>>,
    val kanjiVG: KanjiVG,
    val allWords: AllWordsList
) : PageBuilderBase("/kanji") {
    override fun HEAD.buildHead() {
        script(src = "/collapsible.js") {}
        link("/kanji_details.css", "stylesheet", "text/css")
    }

    private fun FlowContent.renderKanjiSvg(element: Element, size: Int = 109, highlightCompound: String? = null) {
        val newElement = element.clone()
        if (highlightCompound != null) {
            for (elementToHighlight in newElement.getElementsByAttributeValue("kvg:element", highlightCompound)) {
                elementToHighlight.attr("style", "stroke: red;")
            }
        }
        svg {
            attributes["viewBox"] = "0 0 109 109"
            attributes["width"] = "$size"
            attributes["height"] = "$size"
            unsafe {
                +"<g id=\"kvg:StrokePaths\" style=\"fill:none;stroke:#000000;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;\">"
                for (child in newElement.children()) {
                    +child.outerHtml()
                }
            }
        }
    }

    private fun ReadingInfo.SingleReading.jlptTake(n: Int): List<WordEntry> {
        val scoredResult = mutableListOf<Pair<Int, WordEntry>>()
        val restWords = mutableListOf<WordEntry>()
        words.forEach { word ->
            val level = word.getJLPTLevel() ?: run {
                restWords.add(word)
                return@forEach
            }
            scoredResult.add(level to word)
        }
        if (scoredResult.size < n) {
            val rest = n - scoredResult.size
            for (word in restWords.take(rest)) {
                scoredResult.add(0 to word)
            }
        }
        scoredResult.sortByDescending { it.first }
        return scoredResult.map { it.second }
    }

    private fun FlowContent.renderDictionaryInfo(kanji: Char) {
        val readings = getReadingInfoForKanji(kanji, dataset)
        div(classes = "big_kanji") { +"$kanji" }
        readings.commonReadings.forEach { reading ->
            when (reading) {
                is ReadingInfo.SingleReading -> {
                    div(classes = "reading") {
                        +"$reading: ${слово(reading.words.size, true)}"
                    }
                    reading.jlptTake(3).forEach { word ->
                        wordEntry(allWords, word)
                    }
                }
                is ReadingInfo.ReadingCollection -> {
                    div(classes = "reading") {
                        +"$reading: ${(listOf(reading.mainReading) + reading.variations).joinToString(separator = " + ") { it.words.size.toString() }} ${слово(reading.mainReading.words.size)}"
                    }
                    reading.mainReading.jlptTake(3).forEach { word ->
                        wordEntry(allWords, word)
                    }
                    reading.variations.forEach { variation ->
                        variation.jlptTake(1).forEach { word ->
                            wordEntry(allWords, word)
                        }
                    }
                }
            }
        }
        if (readings.specialsWords.isNotEmpty()) {
            div("reading") {
                +"Специальные чтения: ${слово(readings.specialsWords.size, true)}"
            }
            readings.specialsWords.forEach { word ->
                wordEntry(allWords, word)
            }
        }
    }

    private fun Element.toplevelKanjiCompounds(allowDepth: Int = 0): List<Element> {
        val compoundElement = attr("kvg:element")
        val compoundPart = attr("kvg:part")
        val selfList = if (compoundPart in listOf("", "1")) listOf(this) else emptyList()

        return when {
            compoundElement.isNullOrEmpty() -> children().flatMap { it.toplevelKanjiCompounds(allowDepth) }
            allowDepth > 0 -> selfList + children().flatMap { it.toplevelKanjiCompounds(allowDepth - 1) }
            else -> selfList
        }
    }

    private fun FlowContent.renderWritingInfo(kanji: Char) {
        val kanjiElement = kanjiVG.getElementForKanji(kanji)
        renderKanjiSvg(kanjiElement)
        br()
        for (topLevelElements in kanjiElement.toplevelKanjiCompounds(1)) {
            val compoundElement = topLevelElements.attr("kvg:element")
            val kanjiWithCompound = kanjiVG.getKanjiWithCompound(compoundElement)
            if (kanjiWithCompound.size <= 1)
                continue

            renderKanjiSvg(kanjiElement, size = 50, highlightCompound = compoundElement)
            +":"
            var index = 0
            for (otherKanji in kanjiWithCompound) {
                if (otherKanji == kanji)
                    continue

                if (index > 10) {
                    +"..."
                    break
                }

                val otherKanjiElement = kanjiVG.getElementForKanji(otherKanji)
                renderKanjiSvg(otherKanjiElement, size = 50, highlightCompound = compoundElement)
                index++
            }
            br()
        }
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        val kanji = call.parameters["c"]!!.single()
        div("flexRow") {
            div("flexColumn2") {
                renderDictionaryInfo(kanji)
            }
            div("flexColumn2") {
                renderWritingInfo(kanji)
            }
        }

//        val kanjiList = "交通動乗降運転帰発着漢字文教勉習英考研究問題試験質合答用紙意".toCharArray().toList()
//        val wordsSet = mutableSetOf<WordEntry>()
//        val wordsTextSet = mutableSetOf<String>()
//        for (kanji in kanjiList) {
//            val words = dataset[kanji] ?: continue
//            for (word in words) {
//                if (word.getJLPTLevel() == null)
//                    continue
//
//                if (word.text.count { it.isKanji } <= 1)
//                    continue
//
//                if (word.text.any { it.isKanji && it !in kanjiList })
//                    continue
//
//                wordsSet.add(word)
//                wordsTextSet.add(word.text)
//            }
//        }
//
//        for (word in wordsSet) {
//            wordEntry(allWords, word)
//        }
//        for (word in wordsTextSet) {
//            div { +word }
//        }
    }
}