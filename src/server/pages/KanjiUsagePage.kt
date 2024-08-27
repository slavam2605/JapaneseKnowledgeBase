package server.pages

import TxtWordEntry
import io.ktor.server.application.ApplicationCall
import kotlinx.html.*

class KanjiUsagePage(val words: List<TxtWordEntry>) : PageBuilderBase("/kanji_usage") {
    private fun FlowContent.wordEntry(word: TxtWordEntry) {
        div {
            ruby {
                +word.kanjiOrKana
                rt {
                    +word.kana
                }
            }
            unsafe {
                +word.definition
            }
        }
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        val kanji = call.parameters["c"]!!.single()
        for (word in words) {
            if (kanji !in word.kanji)
                continue

            wordEntry(word)
        }
    }
}