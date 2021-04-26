package utils

import org.jsoup.nodes.Element
import server.KanjiVG

fun KanjiVG.kanjiSimilarity(k1: Char, k2: Char): Double {
    val (size1, size2, match) = elementsSimilarity(getElementForKanji(k1), getElementForKanji(k2))
    return 2.0 * match / (size1 + size2)
}

private fun elementsSimilarity(e1: Element, e2: Element): Triple<Int, Int, Int> {
    val c1 = e1.children().toMutableList()
    val c2 = e2.children().toMutableList()
    val matchResult = mutableListOf<Pair<Element, Element?>>()
    TODO()
}