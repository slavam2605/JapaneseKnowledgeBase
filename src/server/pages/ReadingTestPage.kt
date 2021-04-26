package server.pages

import dict.AllWordsList
import dict.JMDict
import dict.WordEntry
import dict.jishoDataset
import io.ktor.application.ApplicationCall
import kotlinx.html.*
import server.notLearnedKanjiList
import utils.isKanji
import kotlin.random.Random

class ReadingTestPage(val allWordsList: AllWordsList) : PageBuilderBase("/reading_test") {
    init {
        cachedAllWords = allWordsList
    }

    override fun HEAD.buildHead() {
        script(src = "/collapsible.js") {}
        link("/reading_test.css", "stylesheet", "text/css")
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        val addedWords = mutableSetOf<WordEntry>()
        repeat(1000) {
            randomWordEntry(addedWords)
        }
    }

    private fun FlowContent.randomWordEntry(addedWords: MutableSet<WordEntry>) {
        while (true) {
            val index = random.nextInt(filteredWords.size)
            val word = filteredWords[index]
            if (word in addedWords)
                continue

            addedWords.add(word)
            div("reading_entry") {
                +word.text
            }
            break
        }
    }

    companion object {
        private lateinit var cachedAllWords: AllWordsList
        private val filteredWords by lazy {
            val learnedKanji = jishoDataset.keys - notLearnedKanjiList
            JMDict.instance.wordsMap.asSequence()
                .flatMap { it.value.asSequence() }
                .map { cachedAllWords.findWordWithReading(it) }
                .filter { it.text.all { c -> !c.isKanji || c in learnedKanji } }
                .filter { it.text.any { c -> c.isKanji } }
                .filter { (it.getJLPTLevel() ?: 0) >= 2 }
                .toList()
        }

        private val random = Random(System.currentTimeMillis())
    }
}