package server.pages

import TxtWordEntry
import dict.WordEntry
import io.ktor.server.application.ApplicationCall
import kotlinx.html.BODY
import kotlinx.html.HEAD
import kotlinx.html.a
import kotlinx.html.link
import server.notLearnedKanjiList
import utils.KanjiLists.jouyou
import utils.isKanji

class KanjiMapPage(val dataset: Map<Char, List<WordEntry>>, val words: List<TxtWordEntry>) : PageBuilderBase("/map") {
    override fun HEAD.buildHead() {
        link("/kanji_map.css", "stylesheet", "text/css")
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        val kanjiUsageMap = mutableMapOf<Char, Int>()
        for (word in words) {
            for (c in word.kanji) {
                if (!c.isKanji)
                    continue

                kanjiUsageMap.compute(c) { _, x -> x?.let { it + 1 } ?: 1 }
            }
        }

        for (kanji in jouyou) {
            kanjiItem(kanji, kanji in dataset && kanji !in notLearnedKanjiList, kanjiUsageMap.getOrDefault(kanji, 0))
        }
    }

    private fun BODY.kanjiItem(kanji: Char, learned: Boolean, inWordsCount: Int) {
        when {
            learned -> {
                a("/kanji?c=$kanji", classes = "kanjiMapItem learnedItem") {
                    +"$kanji"
                }
            }
            inWordsCount > 0 -> {
                a("/kanji_usage?c=$kanji", classes = "kanjiMapItem inWordsItem") {
                    +"$kanji"
                }
            }
            else -> {
                a("https://jisho.org/search/$kanji%20%23kanji", classes = "kanjiMapItem") {
                    +"$kanji"
                }
            }
        }
    }
}