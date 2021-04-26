package server

import TxtWordsListProcessor
import dict.AllWordsList
import dict.MeaningEntry
import dict.WordEntry
import dict.WordEntryImpl
import kotlinx.html.*
import utils.exportedFilePath
import utils.isKanji
import utils.resolveResource
import utils.txtWordsFile
import java.io.File

private val allN45Words = TxtWordsListProcessor(resolveResource("jlpt_n5+n4_words.txt")).readSimpleList()
private val missingWords = TxtWordsListProcessor(resolveResource(txtWordsFile)).readSimpleList()
private val deckWords = TxtWordsListProcessor(File(exportedFilePath)).readExportedList() + allN45Words

fun FlowContent.wordWithFurigana(word: WordEntry, hideKanji: Boolean = false, showFurigana: Boolean = true, block: RUBY.() -> Unit = {}) {
    ruby {
        block()
        if (word.text.isNotEmpty()) {
            word.text.forEachIndexed { index, kanji ->
                if (hideKanji && kanji.isKanji) {
                    +"＿"
                } else {
                    +kanji.toString()
                }
                if (showFurigana) {
                    val furigana = word.furigana.getOrNull(index) ?: return@forEachIndexed
                    rt { +furigana }
                }
            }
        } else {
            +word.getReading()
        }
    }
}

private fun getWordStyle(word: WordEntry): String? {
    if (deckWords.any { w -> w.sameWord(word) } && missingWords.all { w -> !w.sameWord(word) })
        return null

    return if (word.getJLPTLevel() == 3)
        "border-bottom: orange 3px dashed"
    else if ((word.getJLPTLevel() ?: 0) > 3)
        "border-bottom: gray 3px dashed"
    else null
}

fun FlowContent.wordEntry(allWords: AllWordsList, sourceWord: WordEntry, hideKanji: Boolean = false, showFurigana: Boolean = true) {
    val word = allWords.findWordWithReading(sourceWord)
    div(classes = "word_entry") {
        if (word.grammarInfo.isNotEmpty()) {
            div(classes = "word-grammar-info") {
                +word.grammarInfo.joinToString(separator = "; ") { it.prettyDescription }
            }
        }
        word.getJLPTLevel()?.let {
            span("jlpt-n$it-label") {
                +"N$it:"
            }
            +" "
        }
        wordWithFurigana(word, hideKanji=hideKanji, showFurigana=showFurigana) {
            getWordStyle(word)?.let { st ->
                style = st
            }
        }
        val firstTags = word.meanings.filterIsInstance<MeaningEntry.MeaningTags>().firstOrNull()
        val firstMeaning = word.meanings.filterIsInstance<MeaningEntry.MeaningMeaning>().firstOrNull()
        +" – ${firstTags?.let { "[$it] " } ?: ""}${firstMeaning}"
        val visibleCount = listOfNotNull(firstTags, firstMeaning).size
        if (visibleCount < word.meanings.size) {
            button(classes = "collapsible") { +"..." }
            div(classes = "content") {
                unsafe {
                    +word.meanings.drop(visibleCount).joinToString("<br>")
                }
            }
        }
    }
}