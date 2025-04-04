package server.pages

import io.ktor.server.application.*
import kotlinx.html.BODY
import kotlinx.html.div
import kotlinx.html.hr
import org.jsoup.nodes.Element
import server.KanjiVG

class SimilarKanjiPage(
    val kanjiVG: KanjiVG
    ) : PageBuilderBase("/similar_kanji") {
    override fun BODY.buildPage(call: ApplicationCall) {
        val kanji = call.parameters["c"]!!.single()
        val similarKanji = sortSimilarKanji(kanji, findSimilarKanji(kanji))
        div { +"$kanji" }
        hr { }
        for (otherKanji in similarKanji) {
            div { +"$otherKanji" }
        }
    }

    private fun kanjiDifference(a: Char, b: Char): Int {
        val aTree = buildTree(a)
        val bTree = buildTree(b)
        val aCompounds = mutableSetOf<String>()
        val bCompounds = mutableSetOf<String>()
        aTree.dfs {
            if (it.compound == null) return@dfs false
            aCompounds.add(it.compound)
            true
        }
        bTree.dfs {
            if (it.compound == null) return@dfs false
            bCompounds.add(it.compound)
            true
        }
        val commonCompounds = aCompounds.intersect(bCompounds)
        var difference = 0
        listOf(aTree, bTree).forEach { tree ->
            tree.dfs {
                if (it.compound == null) {
                    difference += it.strokeCount
                    return@dfs false
                }
                if (it.compound in commonCompounds) return@dfs false
                if (it.children.isEmpty()) {
                    difference += it.strokeCount
                }
                true
            }
        }
        return difference
    }

    private fun buildTree(kanji: Char): KanjiCompoundTree {
        val kanjiElement = kanjiVG.getElementForKanji(kanji)
        return buildElementTree(kanjiElement.child(0))
    }

    private fun buildElementTree(element: Element): KanjiCompoundTree {
        return when (element.tagName()) {
            "g" -> {
                val children = element.children().map { buildElementTree(it) }
                val compound = element.attr("kvg:element").ifBlank { null }
                KanjiCompoundTree(compound, children.sumBy { it.strokeCount }, children)
            }
            "path" -> {
                KanjiCompoundTree(null, 1, emptyList())
            }
            else -> error(element.tagName())
        }
    }

    private fun sortSimilarKanji(kanji: Char, set: Set<Char>): List<Char> {
        return set.sortedBy { kanjiDifference(kanji, it) }
    }

    private fun findSimilarKanji(kanji: Char): Set<Char> {
        val compounds = kanjiVG.getKanjiCompounds(kanji)
        val result = mutableSetOf<Char>()
        for (position in KanjiVG.KanjiCompoundPosition.values()) {
            result.addAll(kanjiVG.getKanjiWithCompound("$kanji", position))
        }
        for ((compound, position, depth) in compounds) {
            if (depth > 2 || position == KanjiVG.KanjiCompoundPosition.Unknown) continue
            result.addAll(kanjiVG.getKanjiWithCompound(compound, position))
        }
        return result
    }

    private class KanjiCompoundTree(
        val compound: String?,
        val strokeCount: Int,
        val children: List<KanjiCompoundTree>
    ) {
        fun dfs(block: (KanjiCompoundTree) -> Boolean) {
            if (!block(this)) return
            for (child in children) {
                child.dfs(block)
            }
        }
    }
}