import dict.WordEntry
import utils.*

private val ignoreWordsENAM = setOf(
    "亜人", "唖谷", "阿Q"
)

private fun findErrorsAndRemove(list: MutableList<HistoryPair<String, String>>) {
    fun check(pair: HistoryPair<String, String>): Boolean {
        val kanji = pair.first
        val reading = pair.second
        if (kanji.substring(0, kanji.length - 1) == reading)
            return false

        if (kanji.last().isKanji && reading.last().isKatakana)
            return false

        if (kanji.all { !it.isKatakana } && reading.any { it.isKatakana })
            return false

        return true
    }

    list.removeAll {
        val result = check(it)
        if (!result) {
            println("${it.first} [${it.second}]")
        }
        !result
    }
}

fun resolveENAMReadings(dict: List<ENAMEntry>, words: Map<Char, List<WordEntry>>): Map<Char, List<String>> {
    val list = dict
        .filter { it.reading.isNotEmpty() &&
                    it.text !in knownMistakesInENAM &&
                    it.text !in ignoreWordsENAM &&
                    it.text.any { c -> c in words } }
        .map { HistoryPair(it.text.replaceRepeaters(), it.reading) }
        .toMutableList()
    findErrorsAndRemove(list)
    val result = words.mapValues { (key, _) -> getReadingInfoForKanji(key, words).commonReadings.flatMap {
        when (it) {
            is ReadingInfo.SingleReading -> listOf(it.reading)
            is ReadingInfo.ReadingCollection -> listOf(it.mainReading.reading) + it.variations.map { it.reading }
        }
    }.filter { it.isNotEmpty() }.toMutableList() }.toMutableMap()
    while (list.isNotEmpty()) {
        var changed = false
        for (index in 0 until list.size) {
            changed = changed or tryCutAllByOne(list, index, result)
            changed = changed or tryCutFirst(list, index, result)
            changed = changed or tryCutLast(list, index, result)
            changed = changed or tryCutSingle(list, index, result)
        }
        list.removeIf { it.first.isEmpty() }

        if (!changed) {
            println()
        }
    }
    return result
}

private fun tryCutAllByOne(list: MutableList<HistoryPair<String, String>>, index: Int, result: MutableMap<Char, MutableList<String>>): Boolean {
    val candidate = list[index]
    if (candidate.first.isEmpty())
        return false

    val kanji = candidate.first
    val reading = candidate.second
    if (kanji.length != reading.length ||
        kanji.any { !it.isKanji } ||
        reading.any { it.isSmallHiragana || !it.isHiragana }
    ) {
        return false
    }

    println("$kanji => $reading")
    for (charIndex in 0 until kanji.length) {
        val kanjiChar = kanji[charIndex]
        val newReading = "${reading[charIndex]}"
        val kanjiReadings = result.getOrPut(kanjiChar) { mutableListOf() }
        if (newReading !in kanjiReadings) {
            println("$kanjiChar -> $newReading")
            kanjiReadings.add(newReading)
        }
    }
    list[index] = HistoryPair("", "", candidate, ReductionCause.CUT_ALL_BY_ONE)
    return true
}

private fun String.startsWithReading(reading: String): Boolean {
    return this == reading || startsWith(reading) && this[reading.length] != 'っ'
}

private fun tryCutFirst(list: MutableList<HistoryPair<String, String>>, index: Int, result: MutableMap<Char, MutableList<String>>): Boolean {
    val candidate = list[index]
    if (candidate.first.isEmpty())
        return false

    val kanji = candidate.first[0]
    val readings = result[kanji] ?: kanji.possibleReadings
    val bestReading = readings
        .filter { candidate.second.startsWithReading(it) }
        .maxBy { it.length }
        ?: return false

    list[index] = HistoryPair(
        candidate.first.substring(1),
        candidate.second.substring(bestReading.length),
        candidate,
        ReductionCause.CUT_FIRST
    )
    return true
}

private fun tryCutLast(list: MutableList<HistoryPair<String, String>>, index: Int, result: MutableMap<Char, MutableList<String>>): Boolean {
    val candidate = list[index]
    if (candidate.first.isEmpty())
        return false

    val kanji = candidate.first.last()
    val readings = result[kanji] ?: kanji.possibleReadings
    if (readings.filter { candidate.second.endsWith(it) }.size > 1)
        return false

    for (reading in readings) {
        if (candidate.second.endsWith(reading)) {
            list[index] = HistoryPair(
                candidate.first.substring(0, candidate.first.length - 1),
                candidate.second.substring(0, candidate.second.length - reading.length),
                candidate,
                ReductionCause.CUT_LAST
            )
            return true
        }
    }
    return false
}

private fun tryCutSingle(list: MutableList<HistoryPair<String, String>>, index: Int, result: MutableMap<Char, MutableList<String>>): Boolean {
    val candidate = list[index]
    if (candidate.first.length != 1)
        return false

    val kanji = candidate.first.single()
    if (kanji.isKana)
        return false

    val readings = result.getOrPut(kanji) {  mutableListOf() }
    val reading = candidate.second
    if (reading.isEmpty())
        return false

    if (!readings.contains(reading)) {
        println("$kanji -> $reading")
        if (reading == "う" && kanji == '上') {
            val kek = 12
        }
        readings.add(reading)
    }
    list[index] = HistoryPair("", "", candidate, ReductionCause.CUT_SINGLE)
    return true
}

private fun String.replaceRepeaters(): String {
    val builder = StringBuilder()
    for (index in 0 until length) {
        when {
            index == 0 -> builder.append(this[index])
            this[index] == '々' && this[index - 1].isKanji -> builder.append(this[index - 1])
            this[index] == 'ゝ' && this[index - 1].isKana -> builder.append(this[index - 1])
            this[index] == 'ゞ' && this[index - 1].isKana -> builder.append(this[index - 1].toVoicedHiragana())
            else -> builder.append(this[index])
        }
    }
    return builder.toString()
}

private enum class ReductionCause {
    CUT_FIRST, CUT_LAST, CUT_SINGLE, CUT_ALL_BY_ONE
}

private class HistoryPair<A, B>(
    val first: A,
    val second: B,
    private val previous: HistoryPair<A, B>? = null,
    private val cause: ReductionCause = ReductionCause.CUT_FIRST
) {
    override fun toString() = "($first, $second)"
}