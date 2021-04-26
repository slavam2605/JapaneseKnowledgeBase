package server.pages

import TxtWordsListProcessor
import dict.*
import io.ktor.application.ApplicationCall
import kotlinx.html.*
import server.notLearnedKanjiList
import server.wordEntry
import utils.*
import java.io.File

class UnknownWordsPage(val dataset: Map<Char, List<WordEntry>>, val allWords: AllWordsList) : PageBuilderBase("/unknown_words") {
    private val allN45Words = TxtWordsListProcessor(resolveResource("jlpt_n5+n4_words.txt")).readSimpleList()
    private val missingWords = TxtWordsListProcessor(resolveResource(txtWordsFile)).readSimpleList()
    private val deckWords = TxtWordsListProcessor(File(exportedFilePath)).readExportedList() + allN45Words

    private fun isLearned(kanji: Char) =
        kanji in dataset && kanji !in notLearnedKanjiList

    override fun HEAD.buildHead() {
        script(src = "/collapsible.js") {}
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        val showMissing = call.parameters.contains("missing")
        val result = mutableMapOf<String, WordEntry>()
        if (showMissing) {
            missingWords.associateByTo(result, { it.kanjiOrKana }) { txtWord ->
                allWords.tryFindWordByTxtEntry(txtWord)
                    ?: WordEntryImpl(
                        txtWord.kanji,
                        listOf(txtWord.kana),
                        listOf(MeaningEntry.MeaningMeaning(txtWord.definition, emptyList())),
                        emptyList(),
                        emptyList()
                    )
            }
        } else {
            dataset.forEach { (kanji, words) ->
                if (kanji in notLearnedKanjiList)
                    return@forEach

                for (word in words) {
                    if ((word.getJLPTLevel() ?: 0) < 3 ||
                        deckWords.find { it.sameWord(word) } != null
                    ) continue

                    result[word.text] = word
                }
            }
        }

        val sortedResult = result.values.sortedByDescending {
            (it.getJLPTLevel() ?: 0) * 1000 - it.text.filter { c -> c.isKanji && !isLearned(c) }.length
        }.map {
            allWords.findWordWithReading(it)
        }

        val usedWords = hashSetOf<WordEntry>()
        val verbs = extractWordsByPOS(sortedResult, usedWords, PartOfSpeech.DanVerbs)
        val suruVerbs = extractWordsByPOS(sortedResult, usedWords, PartOfSpeech.SuruVerbs)
        val iAdjectives = extractWordsByPOS(sortedResult, usedWords, PartOfSpeech.IAdjectives)
        val naAdjectives = extractWordsByPOS(sortedResult, usedWords, PartOfSpeech.ADJ_NA)
        val noAdjectives = extractWordsByPOS(sortedResult, usedWords, PartOfSpeech.ADJ_NO)
        val nouns = extractWordsByPOS(sortedResult, usedWords, PartOfSpeech.N)
        val other = sortedResult.filter { it !in usedWords }

        collapsedWordList("Глаголы", verbs)
        collapsedWordList("する-глаголы", suruVerbs)
        collapsedWordList("い-прилагательные", iAdjectives)
        collapsedWordList("な-прилагательные", naAdjectives)
        collapsedWordList("の-прилагательные", noAdjectives)
        collapsedWordList("Существительные", nouns)
        collapsedWordList("Остальные слова", other)
    }

    private fun extractWordsByPOS(words: List<WordEntry>, usedWords: MutableSet<WordEntry>, pos: PartOfSpeech): List<WordEntry> {
        return extractWordsByPOS(words, usedWords, listOf(pos))
    }

    private fun extractWordsByPOS(words: List<WordEntry>, usedWords: MutableSet<WordEntry>, poses: List<PartOfSpeech>): List<WordEntry> {
        val extractedWords = words.filter { it !in usedWords && poses.any { pos -> it.grammarInfo.contains(pos) } }
        usedWords.addAll(extractedWords)
        return extractedWords
    }

    private fun FlowContent.collapsedWordList(listName: String, words: List<WordEntry>) {
        button(classes = "collapsible") {
            style = "font-size: 100%;"
            +"$listName (${слово(words.size, true)})"
        }
        div(classes = "content") {
            for (word in words) {
                wordEntry(allWords, word)
            }
        }
        br {  }
    }
}