package server.pages

import TxtWordsListProcessor
import dict.AllWordsList
import dict.WordEntry
import io.ktor.application.*
import kotlinx.html.*
import server.wordEntry
import utils.KanjiLists
import utils.exportedKanjiWordsPath
import java.io.File

class KanjiWordsJLPTList(
    private val allWords: AllWordsList
) : PageBuilderBase("/kanji_words_list") {
    private val deckKanjiWords = TxtWordsListProcessor(File(exportedKanjiWordsPath))
        .readExportedKanjiList()
        .map { it.kanji }
        .toSet()
    private val kanjiSet = KanjiLists.getJlptKanji(3).toSet()
    private val filteredWords = allWords.words.mapNotNull { (_, list) ->
        for (word in list) {
            if (shouldSkip(word)) continue
            return@mapNotNull word
        }
        null
    }

    override fun HEAD.buildHead() {
        script(src = "/collapsible.js") {}
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        renderKanjiWords(5)
        renderKanjiWords(4)
        renderKanjiWords(3)
    }

    private fun shouldSkip(word: WordEntry): Boolean {
        return word.isKanaOnly() || word.isAllArchaisms() ||
                word.text.all { it !in kanjiSet } || (word.getJLPTLevel() ?: 0) < 3 ||
                word.text.removeSuffix("する") in deckKanjiWords || (word.text + "する") in deckKanjiWords
    }

    private fun BODY.renderKanjiWords(targetJlptLevel: Int) {
        button(classes = "collapsible") {
            style = "font-size: 100%;"
            +"JLPT $targetJlptLevel"
        }
        div(classes = "content") {
            filteredWords.forEach { word ->
                if (word.getJLPTLevel() != targetJlptLevel) return@forEach
                wordEntry(allWords, word)
            }
        }
        br { }
    }
}