package server.pages

import io.ktor.server.application.*
import kotlinx.html.BODY
import kotlinx.html.span
import org.jsoup.nodes.Element
import server.KanjiVG
import utils.KanjiLists
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter

class KanjiOrderPage(
    val kanjiVG: KanjiVG
) : PageBuilderBase("/kanji_order") {
    /**
     * @param block returns `true` if subtree needs to be traversed deeper
     */
    private fun Element.traverseKanjiComponents(skipSelf: Boolean = true, block: (String) -> Boolean) {
        val compoundElement = attr("kvg:element")
        val compoundPart = attr("kvg:part")

        // Skip subtree if kvg:part is 2, 3 and so on -- it was already processed in another subtree
        if (!compoundPart.isNullOrEmpty() && compoundPart != "1") {
            return
        }

        val continueTraversal = when {
            skipSelf -> true
            compoundElement.isNullOrEmpty() -> true
            else -> block(compoundElement)
        }
        if (!continueTraversal) {
            return
        }

        val continueSkipSelf = skipSelf && tagName().equals("kanji", ignoreCase = true)
        children().forEach {
            it.traverseKanjiComponents(skipSelf = continueSkipSelf, block = block)
        }
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        val allKanjiSet = KanjiLists.jouyou.toSet() +
                KanjiLists.getJlptKanji(5).toSet() +
                KanjiLists.getJlptKanji(4).toSet() +
                KanjiLists.getJlptKanji(3).toSet() +
                KanjiLists.getJlptKanji(2).toSet() +
                KanjiLists.getJlptKanji(1).toSet()
        val graphEdges = mutableMapOf<Char, MutableSet<Char>>()

        val start = System.currentTimeMillis()

        allKanjiSet.forEach { kanji ->
            val kanjiElement = kanjiVG.getElementForKanji(kanji)
            val edges = graphEdges.getOrPut(kanji) { mutableSetOf() }
            kanjiElement.traverseKanjiComponents {
                // Skipping complex two-char surrogates like 𠂊, 𠂤, 𠂢, 𠔉, 𦥑
                if (it.length != 1) {
                    return@traverseKanjiComponents true
                }

                // Check if subelement is a part of a kanji set
                val kanjiChar = it.single()
                if (kanjiChar in allKanjiSet) {
                    edges.add(kanjiChar)
                    return@traverseKanjiComponents false
                }

                // Continue traversing the subtree if no match was found
                true
            }
        }

        // Topological Sort
        val visited = mutableSetOf<Char>()
        val resultStack = mutableListOf<Char>()

        fun dfs(node: Char) {
            if (node in visited) {
                return
            }
            visited.add(node)
            graphEdges[node]?.forEach { neighbor ->
                dfs(neighbor)
            }
            resultStack.add(node)
        }

        val preferredOrderKanjiList = (1..5).reversed().flatMap { KanjiLists.getJlptKanji(it) } + KanjiLists.jouyou
        preferredOrderKanjiList.forEach { kanji ->
            if (kanji !in visited) {
                dfs(kanji)
            }
        }

        val sortedKanji = resultStack
        sortedKanji.forEach { kanji ->
            span {
                +"$kanji"
            }
        }

//        readWriteFile(sortedKanji)

        println("Took: ${System.currentTimeMillis() - start} ms")
    }

    private fun BODY.readWriteFile(kanjiOrder: List<Char>) {
        val file = File("/Users/Vyacheslav.Moklev/日本語__Kanji__Kanji writing copy.txt")
        val text = file.readText()
        val headerLines = text.lines().take(2)
        val headerSize = headerLines.sumOf { it.length } + 2
        val textNoHeader = text.drop(headerSize)

        val parts = textNoHeader.smartSplit('\t', '\n', 7)
        check(parts.size % 7 == 0)

        val updatedNotes = mutableListOf<List<String>>()
        val notesCount = parts.size / 7
        for (noteIndex in 0 until notesCount) {
            val noteParts = parts.subList(noteIndex * 7, (noteIndex + 1) * 7).toMutableList()
            val kanjiIndex = kanjiOrder.indexOf(noteParts[0].single())
            val formattedIndex = "%05d".format(kanjiIndex)
            noteParts[6] = formattedIndex
            updatedNotes.add(noteParts.toList())
        }

        val fileOut = File("/Users/Vyacheslav.Moklev/日本語__Kanji__Kanji writing.txt")
        OutputStreamWriter(FileOutputStream(fileOut), Charsets.UTF_8).use { writer ->
            writer.write(headerLines[0] + "\n")
            writer.write(headerLines[1] + "\n")
            updatedNotes.forEach { note ->
                note.forEachIndexed { index, part ->
                    if (index > 0) {
                        writer.write("\t")
                    }
                    writer.write(part)
                }
                writer.write("\n")
            }
        }
    }

    private fun String.smartSplit(del1: Char, del2: Char, countMod: Int): List<String> {
        var counter = 0
        fun currentDel(): Char {
            return if (counter == countMod - 1) del2 else del1
        }

        var lastIndex = 0
        val result = mutableListOf<String>()
        for (index in 0 until length) {
            if (this[index] == currentDel()) {
                result.add(this.substring(lastIndex, index))
                counter = (counter + 1) % countMod
                lastIndex = index + 1
            }
        }

        return result
    }
}