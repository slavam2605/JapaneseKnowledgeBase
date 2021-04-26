import dict.MeaningEntry
import dict.MeaningTag
import dict.WordEntry
import dict.WordEntryImpl
import org.jsoup.nodes.Document
import utils.fixKnownMistakes
import java.io.File
import java.io.FileWriter
import kotlin.math.roundToInt

fun readWordsFile(file: File): MutableMap<Char, MutableList<WordEntry>> {
    val openTagPattern = "<start kanji=(.?)>".toPattern()
    val closeTagPattern = "<end kanji=(.?)>".toPattern()
    val lines = file.readLines()
    val result = linkedMapOf<Char, MutableList<WordEntry>>()
    var currentKanji = '\u0000'
    var currentList = mutableListOf<WordEntry>()
    for (line in lines) {
        if (line.isBlank())
            continue

        val openMatcher = openTagPattern.matcher(line)
        if (openMatcher.matches()) {
            currentKanji = openMatcher.group(1)[0]
            continue
        }

        val closeMatcher = closeTagPattern.matcher(line)
        if (closeMatcher.matches()) {
            if (currentKanji != closeMatcher.group(1)[0])
                throw IllegalArgumentException("Kanji doesn't match: $currentKanji and ${closeMatcher.group(1)[0]}")

            result[currentKanji] = currentList
            currentKanji = '\u0000'
            currentList = mutableListOf()
            continue
        }

        try {
            val parsedEntry = WordEntryImpl.readFromString(line)
            currentList.add(parsedEntry)
        } catch (e: Exception) {
            System.err.println("Failed to parse string: $line")
        }
    }
    return result.apply { fixKnownMistakes(this) }
}

private fun getWordsPage(query: String, page: Int): Document? {
    return getDocumentFromUrl("https://jisho.org/search/$query?page=$page")
}

private fun Document.parseWordsPage(): List<WordEntry> {
    val wordBlocks = select("#primary div.concept_light.clearfix")
    return wordBlocks.map { block ->
        val furiganaElement = block.select("div.concept_light-readings span.furigana").single()
        val furigana = furiganaElement.children().mapNotNull { child ->
            if (child.tag().name != "span")
                null
            else
                child.text()
        }.let { spanList ->
            if (spanList.isEmpty()) {
                listOf(furiganaElement.select("rt").joinToString(separator = "") { it.text() })
            } else spanList
        }
        val text = block.select("span.text").single().text()
        val tags = block.select("span.concept_light-tag").map { tagElement ->
            tagElement.text()
        }
        val meanings = block.select("div.meanings-wrapper > div").mapNotNull { meaningElement ->
            when (meaningElement.className()) {
                "meaning-tags" -> MeaningEntry.MeaningTags(meaningElement.text())
                "meaning-wrapper" -> {
                    val meaningMeaning = meaningElement.select("span.meaning-meaning").singleOrNull()
                        ?: return@mapNotNull null

                    val supplementalInfo = meaningElement.select("span.supplemental_info > span").map {
                        MeaningTag(it.text(), it.classNames() - setOf("sense-tag"))
                    }
                    MeaningEntry.MeaningMeaning(meaningMeaning.text(), supplementalInfo)
                }
                else -> {
                    System.err.println("Unknown meaning class: ${meaningElement.className()}")
                    null
                }
            }
        }
        WordEntryImpl(text, furigana, meanings, emptyList(), tags)
    }
}

fun downloadWordsForQuery(query: String, maxPageCount: Int = 200, handler: (List<WordEntry>) -> Unit) {
    for (pageNumber in 0 until maxPageCount) {
        print("$pageNumber, ")
        val words = getWordsPage(query, pageNumber + 1)?.parseWordsPage() ?: emptyList()
        if (words.isEmpty())
            break

        handler(words)
        if (pageNumber == maxPageCount - 1 && words.isNotEmpty()) {
            System.err.println("Warn: downloaded $maxPageCount pages and it is still not empty")
        }

        Thread.sleep(getNextDelayForDownload())
    }
}

fun downloadCommonWords(file: File) {
    val start = System.currentTimeMillis()
    var currentPage = 0
    file.bufferedWriter().use { writer ->
        downloadWordsForQuery("*%20%23common%20%23words", 2000) { words ->
            for (word in words) {
                writer.write(word.writeToString())
                writer.newLine()
            }

            val elapsed = System.currentTimeMillis() - start
            currentPage++
            val pagesLeft = 1053 - currentPage
            val estimatedTimeLeft = elapsed.toDouble() / currentPage * pagesLeft
            println("Time left: ${(estimatedTimeLeft / 6000).roundToInt() / 10.0} minutes")
        }
    }
}

fun downloadWords(file: File, vararg kanjiToDownload: Char) {
    val result = readWordsFile(file)
    FileWriter(file, true).use { writer ->
        for (kanji in kanjiToDownload) {
            if (kanji in result) {
                System.err.println("Skipping kanji: $kanji")
                continue
            }

            print("$kanji: ")
            val allWords = mutableListOf<WordEntry>()
            downloadWordsForQuery("*$kanji*%20%23words") {
                allWords.addAll(it)
            }
            println()

            writer.write("<start kanji=$kanji>\n")
            for (word in allWords) {
                writer.write("${word.writeToString()}\n")
            }
            writer.write("<end kanji=$kanji>\n")
        }
    }
}