package dict

import fromBase64
import readFromString
import toBase64
import utils.isHiragana
import utils.isKana
import writeToString

interface WordEntry {
    val text: String
    val furigana: List<String>
    val meanings: List<MeaningEntry>
    val grammarInfo: List<PartOfSpeech>
    val extraTags: List<String>

    fun writeToString(): String
    fun matchFurigana(): List<Pair<Char, String>>?
    fun getReading(): String

    fun isCommon(): Boolean {
        return extraTags.contains("Common word")
    }

    fun isKanaOnly(): Boolean {
        val meaningMeanings = meanings.filterIsInstance<MeaningEntry.MeaningMeaning>()
        return meaningMeanings.firstOrNull()?.tags?.any {
            it.tag.contains("kana alone") || it.tag.contains("Usually written using kana alone")
        } == true
    }

    fun isAllArchaisms(): Boolean {
        val meaningMeanings = meanings.filterIsInstance<MeaningEntry.MeaningMeaning>()
        return meaningMeanings.all { meaning -> meaning.tags.any { it.tag.contains("Archaism") } }
    }

    fun getJLPTLevel(): Int? {
        return when {
            extraTags.contains("JLPT N5") -> 5
            extraTags.contains("JLPT N4") -> 4
            extraTags.contains("JLPT N3") -> 3
            extraTags.contains("JLPT N2") -> 2
            extraTags.contains("JLPT N1") -> 1
            else -> null
        }
    }
}

class WordEntryImpl(
    override var text: String,
    override var furigana: List<String>,
    override var meanings: List<MeaningEntry>,
    override var grammarInfo: List<PartOfSpeech>,
    override var extraTags: List<String>
) : WordEntry {
    companion object {
        fun readFromString(line: String): WordEntry {
            val (sText, sFurigana, sMeanings, sTags) = line.split(":we:", limit = 4)
            val text = sText.fromBase64()
            val furigana = readFromString(sFurigana, "|") { it }
            val meanings =
                readFromString(sMeanings, "|") { MeaningEntry.readFromString(it) }
            val tags = readFromString(sTags, "|") { it }
            return WordEntryImpl(text, furigana, meanings, emptyList(), tags)
        }
    }

    override fun writeToString(): String {
        val sText = text.toBase64()
        val sFurigana = furigana.writeToString("|") { it }
        val sMeanings = meanings.writeToString("|") { it.writeToString() }
        val sTags = extraTags.writeToString("|") { it }
        return "$sText:we:$sFurigana:we:$sMeanings:we:$sTags"
    }

    override fun matchFurigana(): List<Pair<Char, String>>? {
        if (furigana.size != text.length)
            return null

        val matchList = mutableListOf<Pair<Char, String>>()
        for (index in furigana.indices) {
            val furiganaElement = furigana[index]
            val textElement = text.getOrNull(index)
                ?: return null

            if ((furiganaElement == "") != textElement.isKana)
                return null

            matchList.add(textElement to furiganaElement)
        }
        return matchList
    }

    override fun getReading(): String {
        val builder = StringBuilder()
        for (index in furigana.indices) {
            val furiganaElement = furigana[index]
            val textElement = text.getOrNull(index)
            if (furiganaElement.isEmpty() && textElement?.isHiragana == true) {
                builder.append(textElement)
            } else {
                builder.append(furiganaElement)
            }
        }
        return builder.toString()
    }

    override fun toString(): String {
        return "$text (${furigana.joinToString(separator = "")}): [${meanings.getOrNull(0)}] ${meanings.getOrNull(1)}"
    }
}

sealed class MeaningEntry {
    companion object {
        const val tagsKey = "MeaningTags"
        const val meaningKey = "MeaningMeaning"

        fun readFromString(value: String): MeaningEntry {
            val (key) = value.split(":me:", limit = 2)
            return when (key) {
                tagsKey -> {
                    val (_, base64Value) = value.split(":me:", limit = 2)
                    val decodedValue = base64Value.fromBase64()
                    MeaningTags(decodedValue)
                }
                meaningKey -> {
                    val (_, base64Value, encodedTags) = value.split(":me:", limit = 3)
                    val decodedValue = base64Value.fromBase64()
                    val tags = readFromString(encodedTags, ":mts:") { encodedTag ->
                        val (tagBase64, classList) = encodedTag.split(":mt:", limit = 2)
                        val decodedTag = tagBase64.fromBase64()
                        val decodedClassList = readFromString(classList, ":mtc:") { it }
                        MeaningTag(decodedTag, decodedClassList.toSet())
                    }
                    MeaningMeaning(decodedValue, tags)
                }
                else -> error(key)
            }
        }
    }

    class MeaningTags(val tags: String): MeaningEntry() {
        override fun writeToString(): String {
            return "$tagsKey:me:${tags.toBase64()}"
        }

        override fun toString() = tags
    }

    class MeaningMeaning(val meaning: String, val tags: List<MeaningTag>): MeaningEntry() {
        override fun writeToString(): String {
            return "$meaningKey:me:${meaning.toBase64()}:me:${tags.writeToString(":mts:") { "${it.tag.toBase64()}:mt:${it.classes.writeToString(":mtc:") { it }}" }}"
        }

        override fun toString() = meaning
    }

    abstract fun writeToString(): String
}

class MeaningTag(val tag: String, val classes: Set<String>)