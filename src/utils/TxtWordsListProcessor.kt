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

    private inline fun <reified T> File.useLinesSafe(block: (Sequence<String>) -> T): T {
        return try {
            useLines(block = block)
        } catch (e: Exception) {
            System.err.println("Failed to read from ${file.name}")
            e.printStackTrace(System.err)
            return when {
                T::class.java.isAssignableFrom(List::class.java) -> emptyList<Any>() as T
                T::class.java.isAssignableFrom(Set::class.java) -> emptySet<Any>() as T
                else -> error("Failed to return an empty value of type ${T::class.java}")
            }
        }
    }

    fun readExportedList(): List<TxtWordEntry> {
        return file.useLinesSafe { lines ->
            lines.map { line ->
                val (kana, kanji, definition, examples, _, type, _) = line.split("\t")
                TxtWordEntry(kana, kanji, type, definition, readExamples(examples))
            }.toList()
        }
    }

    fun readExportedKanjiList(): List<TxtWordEntry> {
        return file.useLinesSafe { lines ->
            lines.mapNotNull { line ->
                if (line.startsWith("#")) return@mapNotNull null
                val (kanji, kana, definition) = line.split("\t")
                TxtWordEntry(kana, kanji, "", definition, emptyList())
            }.toList()
        }
    }

    fun readExportedKanjiSet(): Set<String> {
        return file.useLinesSafe { lines ->
            lines
                .filter { !it.startsWith("#") }
                .mapNotNull { it.split("\t").firstOrNull() }
                .toSet()
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