package server.pages

import dict.*
import io.ktor.server.application.ApplicationCall
import kotlinx.html.*
import utils.pusaUnknownN5N4Kanji
import server.notLearnedKanjiList
import utils.KanjiLists.getJlptKanji
import utils.isKanji
import kotlin.random.Random

class WritingTestPage(val allWordsList: AllWordsList) : PageBuilderBase("/writing_test") {
    override fun HEAD.buildHead() {
        script(src = "/collapsible.js") {}
        link("/writing_test.css", "stylesheet", "text/css")
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        val pusaMode = call.parameters["pusa"] != null
        val addedEntry = mutableSetOf<WordEntry>()
        while (addedEntry.size < 70) {
            randomWordEntry(addedEntry, pusaMode)
        }
        val entryList = addedEntry.toMutableList()
        for (wordList in arrangeWords(entryList)) {
            for (word in wordList) {
                testWordEntry(word, pusaMode)
            }
//            br { }
        }
    }

    private fun arrangeWords(wordList: MutableList<WordEntry>): List<List<WordEntry>> {
        val totalWidth = 2500
        val wordGap = 120
        val result = mutableListOf<List<WordEntry>>()

        var currentList = mutableListOf<WordEntry>()
        var leftWidth = totalWidth

        fun getBestWord(): WordEntry? {
            return wordList
                .filter { estimateWordLength(it) <= leftWidth }
                .maxByOrNull { estimateWordLength(it) }
        }

        while (wordList.isNotEmpty()) {
            if (getBestWord() == null) {
                result.add(currentList)
                currentList = mutableListOf()
                leftWidth = totalWidth
            }

            val nextWord = getBestWord()!!
            currentList.add(nextWord)
            wordList.remove(nextWord)
            leftWidth -= estimateWordLength(nextWord) - wordGap
        }
        result.add(currentList)
        return result
    }

    private fun estimateWordLength(word: WordEntry): Int {
        val cellWidth = 180
        val hiraganaWidth = 180
        val letterWidth = 41
        val japaneseLetterWidth = 90
        val translationGap = 100

        var totalWidth = 0
        for (char in word.text) {
            if (char.isKanji)
                totalWidth += cellWidth
            else
                totalWidth += hiraganaWidth
        }

        val (shortMeaning, _) = extractShortMeaning(word)
        for (char in shortMeaning) {
            if (char in 'а'..'я' ||
                char in 'A'..'Я' ||
                char in '0'..'9' ||
                char == '(' ||
                char == ')' ||
                char == '{' ||
                char == '}' ||
                char == ':' ||
                char == '-' ||
                char == '.' ||
                char == ' ' ||
                char == 'ё' ||
                char == 'Ё' ||
                char == '?'
            ) {
                totalWidth += letterWidth
            } else {
                println(char)
                totalWidth += japaneseLetterWidth
            }
        }

        return totalWidth + translationGap
    }

    private fun randomWordEntry(addedEntry: MutableSet<WordEntry>, pusaMode: Boolean) {
        val pickWordsList = if (pusaMode) pusaFilteredWords else filteredWords
        while (true) {
            val index = random.nextInt(pickWordsList.size)
            val word = pickWordsList[index]
            if (word in addedEntry)
                continue

            addedEntry.add(word)
            break
        }
    }

    private fun FlowContent.testWordEntry(word: WordEntry, pusaMode: Boolean) {
        val (kek, kke) = extractShortMeaning(word)
        div("writing_test_entry") {
            word.text.forEachIndexed { index, kanji ->
                if (kanji.isKanji) {
                    div("furigana_block") {
                        val furigana = word.furigana.getOrNull(index) ?: ""
                        div("furigana_entry") {
                            +furigana
                        }
                        div("kanji_box") {
                            if (pusaMode) {
                                +"$kanji"
                            }
                        }
                    }
                } else {
                    span("hiragana_box") {
                        +"$kanji"
                    }
                }
            }
            span("test_entry_meaning") {
                +kek
//                button(classes = "collapsible") { +"..." }
//                div(classes = "content") {
//                    +kke
//                }
            }
        }
    }

    private fun extractShortMeaning(word: WordEntry): Pair<String, String> {
        val candidates = word.meanings
            .filterIsInstance<MeaningEntry.MeaningMeaning>()
            .mapNotNull { meaningEntry ->
                val firstMeaning = meaningEntry.meaning
                val shortPart = firstMeaning
                    .removePrefix("1) ")
                    .removePrefix("2) ")
                    .removePrefix("3) ")
                    .removePrefix("1. ")
                    .removePrefix("a) ")
                    .replace("\\([^()]*?\\)".toRegex(), "")
                    .replace("\\([^()]*?\\)".toRegex(), "")
                    .split(",", ";")[0]

                if (shortPart.any { it.lowercaseChar() in 'а'..'я' || it.lowercaseChar() in 'a'..'z' })
                    shortPart to firstMeaning
                else
                    null
            }
        return candidates.firstOrNull { it.first.length < 15 }
            ?: candidates.minByOrNull { it.first.length }
            ?: ("" to "")
    }

    companion object {
        private val filteredWords by lazy {
            val learnedKanji = jishoDataset.keys - notLearnedKanjiList
            val dict = JMDict.instance
            dict.wordsMap.asSequence()
                .flatMap { it.value.asSequence() }
                .filter { it.text.all { c -> !c.isKanji || c in learnedKanji } }
                .filter { it.getJLPTLevel()?.let { it >= 3 } == true }
                .toList()
        }

        private val pusaFilteredWords by lazy {
            val learnedKanji = (getJlptKanji(5) + getJlptKanji(4)).filter { it !in pusaUnknownN5N4Kanji }
            val dict = JMDict.instance
            dict.wordsMap.asSequence()
                .flatMap { it.value.asSequence() }
                .filter { it.text.all { c -> !c.isKanji || c in learnedKanji } }
                .filter { it.getJLPTLevel()?.let { it >= 3 } == true }
                .toList()
        }

        private val random = Random(System.currentTimeMillis())
    }
}