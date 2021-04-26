package server

import org.jsoup.Jsoup
import org.jsoup.nodes.Element
import org.jsoup.nodes.Node
import org.jsoup.select.NodeVisitor
import utils.resolveResource

class KanjiVG(allKanji: Set<Char>) {
    private val compoundToKanji = mutableMapOf<String, MutableList<Char>>()
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
                if (kanji in allKanji) {
                    kanjiToElement[kanji] = node as Element
                }
            }

            override fun head(node: Node?, depth: Int) = Unit
        })

        for (kanji in allKanji) {
            val element = kanjiToElement[kanji]!!
            element.traverse(object : NodeVisitor {
                override fun head(node: Node, depth: Int) {
                    val kvgElement = node.attr("kvg:element")
                    if (kvgElement.isNullOrEmpty())
                        return

                    compoundToKanji.getOrPut(kvgElement, { mutableListOf() }).let { list ->
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
        println("KanjiVG was loaded in ${System.currentTimeMillis() - start} ms")
    }

    fun getElementForKanji(kanji: Char) =
        kanjiToElement[kanji]!!

    fun getKanjiWithCompound(compound: String) =
        compoundToKanji[compound]!!
}