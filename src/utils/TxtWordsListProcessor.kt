import dict.WordEntry
import utils.component6
import utils.component7
import utils.splitAnkiHtml
import java.io.File

class TxtWordsListProcessor(val file: File) {
    fun readSimpleList(): List<TxtWordEntry> {
        return file.useLines { lines ->
            lines.drop(1).map { line ->
                val (kana, kanji, type, definition) = line.split("\t").drop(1)
                TxtWordEntry(kana, kanji, type, definition, emptyList())
            }.toList()
        }
    }

    private fun readExamples(text: String): List<String> {
        return text.splitAnkiHtml()
    }

    fun readExportedList(): List<TxtWordEntry> {
        return file.useLines { lines ->
            lines.map { line ->
                val (kana, kanji, definition, examples, _, type, _) = line.split("\t")
                TxtWordEntry(kana, kanji, type, definition, readExamples(examples))
            }.toList()
        }
    }

    companion object {
        fun writeSimpleList(list: List<TxtWordEntry>, file: File) {
            file.bufferedWriter().use { writer ->
                writer.write("#\tKana\tKanji\tType\tDefinition/s")
                list.forEachIndexed { index, word ->
                    writer.newLine()
                    writer.write("${index + 1}\t${word.kana}\t${word.kanji}\t${word.type}\t${word.definition}")
                }
            }
        }
    }
}

data class TxtWordEntry(
    val kana: String,
    val kanji: String,
    val type: String,
    val definition: String,
    val examples: List<String>
) {
    val kanjiOrKana: String
        get() = if (kanji.isEmpty() || kanji == "kana") kana else kanji

    fun sameWord(other: TxtWordEntry): Boolean {
        val thisKana = kana.dropLastWhile { it == '_' }.removeSuffix("する")
        val otherKana = other.kana.dropLastWhile { it == '_' }.removeSuffix("（する）").removeSuffix("・する").removeSuffix("する")
        return thisKana == otherKana
    }

    fun sameWord(other: WordEntry): Boolean {
        return sameWord(TxtWordEntry(other.getReading(), other.text, "", "", emptyList()))
    }
}