package dict

import org.w3c.dom.Element
import org.w3c.dom.NodeList
import utils.PathConstants
import utils.isKanji
import utils.resolveResource
import java.io.File
import java.lang.System.currentTimeMillis
import javax.xml.parsers.DocumentBuilderFactory

class JMDict private constructor(file: File) {
    companion object {
        val instance: JMDict by lazy {
            JMDict(resolveResource(PathConstants.jmDictFile))
        }
    }

    private val _wordsMap = mutableMapOf<String, MutableList<WordEntry>>()
    val wordsMap: Map<String, List<WordEntry>>
        get() = _wordsMap

    init {
        val start = currentTimeMillis()

        val factory = DocumentBuilderFactory.newInstance()
        val builder = factory.newDocumentBuilder()
        val doc = builder.parse(file)

        doc.getElementsByTagName("entry").forEach { entry ->
            val readings = entry.getElementsByTagName("reb").toList().map { it.textContent }

            entry.getElementsByTagName("keb").forEach { element ->
                val writing = element.textContent
                val list = _wordsMap.getOrPut(writing) { mutableListOf() }
                list.add(entry.toWordEntry(writing, readings))
            }
        }

        val diff = currentTimeMillis() - start
        println("JMDict is loaded in $diff ms")
    }

    private fun Element.toWordEntry(writing: String, readings: List<String>): WordEntry {
        val engMeanings = mutableListOf<String>()
        val rusMeanings = mutableListOf<String>()

        getElementsByTagName("gloss").forEach {
            when (it.getAttribute("xml:lang")) {
                "eng" -> engMeanings.add(it.textContent)
                "rus" -> rusMeanings.add(it.textContent)
            }
        }
        val meanings = if (rusMeanings.isNotEmpty()) rusMeanings else engMeanings
        val partOfSpeech = getElementsByTagName("pos").toList().map {
            PartOfSpeech.fromDescription(it.textContent) ?: error("Unknown part of speech: '${it.textContent}'")
        }

        return WordEntryImpl(
            writing,
            readings.firstOrNull()?.let { matchFurigana(writing, it) } ?: emptyList(),
            meanings.map { MeaningEntry.MeaningMeaning(it, emptyList()) },
            partOfSpeech.distinct(),
            emptyList()
        )
    }

    private fun trySplit(char: Char, reading: String): Int? {
        val count = reading.count { it == char }
        return if (count == 1)
            reading.indexOf(char)
        else
            null
    }

    private fun matchFurigana(text: String, reading: String): List<String> {
        text.forEachIndexed { index, char ->
            if (char.isKanji)
                return@forEachIndexed

            val splitIndex = trySplit(char, reading)
                ?: return@forEachIndexed

            val leftMatch = matchFurigana(text.substring(0, index), reading.substring(0, splitIndex))
            val rightMatch = matchFurigana(text.substring(index + 1), reading.substring(splitIndex + 1))
            return leftMatch + listOf("") + rightMatch
        }

        val result = mutableListOf<String>()
        val step = reading.length.toDouble() / text.length
        var position = 0.01
        var intPosition = 0
        for (i in text.indices) {
            position += step
            val newIntPosition = position.toInt()
            result.add(reading.substring(intPosition, newIntPosition))
            intPosition = newIntPosition
        }
        if (intPosition != reading.length) {
            return listOf(reading)
        }
        return result
    }
}

private fun NodeList.toList(): List<Element> {
    val result = mutableListOf<Element>()
    for (i in 0 until length) {
        result.add(item(i) as Element)
    }
    return result
}

private inline fun NodeList.forEach(block: (Element) -> Unit) {
    for (i in 0 until length) {
        block(item(i) as? Element ?: continue)
    }
}