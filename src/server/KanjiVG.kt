package server

import org.jsoup.Jsoup
import org.jsoup.nodes.Element
import org.jsoup.nodes.Node
import org.jsoup.select.NodeVisitor
import utils.resolveResource

class KanjiVG(allKanji: Set<Char>) {
    private val datasetCompoundToKanji = mutableMapOf<String, MutableList<Char>>()
    private val compoundToKanji = mutableMapOf<KanjiCompoundPosition, MutableMap<String, MutableSet<Char>>>()
    private val kanjiToElement = mutableMapOf<Char, Element>()

    init {
        val start = System.currentTimeMillis()

        val document = Jsoup.parse(resolveResource("kanjivg.xml"), "UTF-8")
        
        document.traverse(object : NodeVisitor {
            override fun tail(node: Node, depth: Int) {
                val kvgKanji = node.attr("id")
                if (kvgKanji.isNullOrEmpty() ||
                    !kvgKanji.startsWith("kvg:kanji_") ||
                    kvgKanji.length != "kvg:kanji_".length + 5)
                    return

                val kanji = Integer.parseInt(kvgKanji.substring(kvgKanji.length - 5), 16).toChar()
                kanjiToElement[kanji] = node as Element
            }

            override fun head(node: Node, depth: Int) = Unit
        })

        for (kanji in allKanji) {
            val element = kanjiToElement[kanji]!!
            processDatasetKanjiCompounds(element, kanji)
        }
        for ((kanji, element) in kanjiToElement) {
            processKanjiCompounds(element, kanji)
        }
        println("KanjiVG was loaded in ${System.currentTimeMillis() - start} ms")
    }

    private fun getCompoundPosition(kvgPosition: String?, depth: Int) =
        if (depth == 1) KanjiCompoundPosition.Itself else KanjiCompoundPosition.parse(kvgPosition)

    private fun processKanjiCompounds(element: Element, kanji: Char) {
        element.traverse(object : NodeVisitor {
            override fun head(node: Node, depth: Int) {
                val kvgElement = node.attr("kvg:element")
                if (kvgElement.isNullOrEmpty())
                    return

                val kvgPosition = node.attr("kvg:position")
                val position = getCompoundPosition(kvgPosition, depth)
                val positionMap = compoundToKanji.getOrPut(position) { mutableMapOf() }
                val compoundSet = positionMap.getOrPut(kvgElement) { mutableSetOf() }
                compoundSet.add(kanji)
            }

            override fun tail(node: Node, depth: Int) = Unit
        })
    }

    private fun processDatasetKanjiCompounds(element: Element, kanji: Char) {
        element.traverse(object : NodeVisitor {
            override fun head(node: Node, depth: Int) {
                val kvgElement = node.attr("kvg:element")
                if (kvgElement.isNullOrEmpty())
                    return

                datasetCompoundToKanji.getOrPut(kvgElement) { mutableListOf() }.let { list ->
                    if (kanji !in list) {
                        if ("$kanji" == kvgElement) {
                            list.add(0, kanji)
                        } else {
                            list.add(kanji)
                        }
                    }
                }
            }

            override fun tail(node: Node, depth: Int) = Unit
        })
    }

    fun getElementForKanji(kanji: Char) = kanjiToElement[kanji]!!

    fun getDatasetKanjiWithCompound(compound: String): List<Char> {
        return datasetCompoundToKanji[compound]!!
    }

    fun getKanjiWithCompound(compound: String, position: KanjiCompoundPosition): Set<Char> {
        return compoundToKanji[position]?.get(compound) ?: emptySet()
    }

    fun getKanjiCompounds(kanji: Char): List<Triple<String, KanjiCompoundPosition, Int>> {
        val element = getElementForKanji(kanji)
        val result = mutableListOf<Triple<String, KanjiCompoundPosition, Int>>()
        element.traverse(object : NodeVisitor {
            override fun head(node: Node, depth: Int) {
                val kvgElement = node.attr("kvg:element")
                if (kvgElement.isNullOrEmpty())
                    return

                val kvgPosition = node.attr("kvg:position")
                val position = getCompoundPosition(kvgPosition, depth)
                result.add(Triple(kvgElement, position, depth))
            }

            override fun tail(node: Node, depth: Int) = Unit
        })
        return result
    }

    enum class KanjiCompoundPosition {
        Left, Right, Top, Bottom, Nyo, Tare, Kamae, Unknown, Itself;

        companion object {
            fun parse(position: String?): KanjiCompoundPosition {
                return entries.find { it.name.equals(position, ignoreCase = true) } ?: Unknown
            }
        }
    }
}