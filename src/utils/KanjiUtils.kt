package utils

import dict.MeaningEntry
import dict.WordEntry
import utils.ReadingInfo.ReadingCollection
import utils.ReadingInfo.SingleReading

private fun groupWordsByKanjiReading(kanji: Char, words: List<WordEntry>, wordFilter: (WordEntry) -> Boolean): Map<String, List<WordEntry>> {
    val result = mutableMapOf<String, MutableList<WordEntry>>()
    fun <K, V> MutableMap<K, MutableList<V>>.getOrCreate(key: K): MutableList<V> {
        return getOrPut(key) { mutableListOf() }
    }

    for (word in words) {
        if (!wordFilter(word))
            continue

        val matchResult = word.matchFurigana()
        if (matchResult == null) {
            result.getOrCreate("").add(word)
        } else {
            for ((char, reading) in matchResult) {
                if (char == kanji) {
                    result.getOrCreate(reading).add(word)
                }
            }
        }
    }
    return result
}

private fun getReadingsForKanji(
    kanji: Char,
    wordsMap: Map<Char, List<WordEntry>>,
    includeOnlyCommon: Boolean = true,
    excludeKanaOnly: Boolean = true,
    excludeArchaisms: Boolean = true
): Map<String, List<WordEntry>> {
    val words = wordsMap[kanji]
        ?: return emptyMap()

    return groupWordsByKanjiReading(kanji, words) { word ->
        if (includeOnlyCommon) {
            if (!word.isCommon())
                return@groupWordsByKanjiReading false
        }
        if (excludeKanaOnly) {
            if (word.isKanaOnly())
                return@groupWordsByKanjiReading false
        }
        if (excludeArchaisms) {
            if (word.isAllArchaisms())
                return@groupWordsByKanjiReading false
        }
        true
    }
}

private val startVariationExceptions = setOf("通り")

private fun SingleReading.isStartVariationOf(other: SingleReading, kanji: Char): Boolean {
    if (other.reading[0] !in reading[0].possiblePlainHiragana() || reading.substring(1) != other.reading.substring(1))
        return false

    for (word in words) {
        if (word.text[0] == kanji && word.furigana[0] == reading && word.text !in startVariationExceptions)
            return false
    }
    return true
}

private fun SingleReading.isEndVariationOf(other: SingleReading, kanji: Char): Boolean {
    return reading.last() == 'っ' &&
            reading.substring(0, reading.length - 1) == other.reading.substring(0, other.reading.length - 1)
}

private fun SingleReading.isKunVariationOf(other: SingleReading, kanji: Char): Boolean {
    return reading.substring(0, reading.length - 1) == other.reading
            && Hiragana.fromChar(reading.last())!!.vowel == KanaVowel.I
}

private fun SingleReading.isVariationOf(other: SingleReading, kanji: Char): Boolean {
    return isStartVariationOf(other, kanji) || isEndVariationOf(other, kanji) || isKunVariationOf(other, kanji)
}

fun getReadingInfoForKanji(kanji: Char, wordsMap: Map<Char, List<WordEntry>>): KanjiReadingInfo {
    val rawReadings = getReadingsForKanji(kanji, wordsMap)
    val readings = rawReadings.mapNotNull { (reading, words) ->
        if (reading == "")
            return@mapNotNull null

        SingleReading(reading, words)
    }

    val groupedReadings = readings.mapNotNull { reading ->
        for (other in readings) {
            if (other.reading == reading.reading)
                continue

            if (reading.isVariationOf(other, kanji))
                return@mapNotNull null
        }
        val variations = readings.filter { other ->
            if (other.reading == reading.reading)
                return@filter false

            other.isVariationOf(reading, kanji)
        }
        if (variations.isEmpty())
            reading
        else
            ReadingCollection(reading, variations)
    }

    return KanjiReadingInfo(kanji, groupedReadings, rawReadings[""] ?: emptyList())
}

sealed class ReadingInfo {
    class SingleReading(val reading: String, val words: List<WordEntry>) : ReadingInfo() {
        override fun toString() = reading
    }

    class ReadingCollection(val mainReading: SingleReading, val variations: List<SingleReading>) : ReadingInfo() {
        override fun toString() = "$mainReading (${variations.joinToString()})"
    }
}

class KanjiReadingInfo(
    val kanji: Char,
    val commonReadings: List<ReadingInfo>,
    val specialsWords: List<WordEntry>
)