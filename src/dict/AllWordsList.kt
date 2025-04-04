package dict

import TxtWordEntry
import utils.ENAMDict
import utils.PathConstants.enamDictFile
import utils.resolveResource

class AllWordsList(dataset: Map<Char, List<WordEntry>>) {
    val words = mutableMapOf<String, MutableList<WordEntry>>()
    private val enamDict = ENAMDict(resolveResource(enamDictFile))

    init {
        val jmDict = JMDict.instance
        jmDict.wordsMap.forEach { (key, list) ->
            words[key] = mutableListOf<WordEntry>().apply { addAll(list) }
        }

        fun appendWord(word: WordEntry) {
            val list = words.getOrPut(word.text) { mutableListOf() }
            for (oldWord in list) {
                if (oldWord.getReading() == word.getReading()) {
                    (oldWord as WordEntryImpl).extraTags = (oldWord.extraTags + word.extraTags).distinct()
                    oldWord.furigana = word.furigana
                    return
                }
            }

            list.add(word)
        }

        jishoCommonWords.forEach { word ->
            appendWord(word)
        }

        dataset.forEach { (_, list) ->
            list.forEach {
                appendWord(it)
            }
        }
    }

    fun getWords(text: String): List<WordEntry> = words[text]
        ?: enamDict[text]?.map { WordEntryImpl.fromENAMEntry(it) }
        ?: emptyList()

    fun findWordWithReading(word: WordEntry): WordEntry {
        val newWord = getWords(word.text).find {
            it.getReading() == word.getReading()
        } ?: word
        (word as WordEntryImpl).furigana = word.furigana
        return newWord
    }

    fun tryFindWordByTxtEntry(word: TxtWordEntry): WordEntry? {
        val fixedKanji = word.kanjiOrKana
            .removeSuffix("_")
            .removeSuffix("_")
            .removeSuffix("_")
            .removeSuffix("する")
        val fixedKana = word.kana
            .removeSuffix("_")
            .removeSuffix("_")
            .removeSuffix("_")
            .removeSuffix("する")

        return getWords(fixedKanji).find {
            it.getReading() == fixedKana
        }
    }
}