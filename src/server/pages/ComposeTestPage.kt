package server.pages

import TxtWordEntry
import dict.AllWordsList
import io.ktor.server.application.ApplicationCall
import kotlinx.html.BODY
import kotlinx.html.div
import kotlinx.html.style
import server.wordWithFurigana
import kotlin.random.Random

class ComposeTestPage(val words: List<TxtWordEntry>, val allWords: AllWordsList) : PageBuilderBase("/compose_test") {
    override fun BODY.buildPage(call: ApplicationCall) {
        repeat(10) {
            val index = Random.nextInt(words.size)
            val txtWord = words[index]
            val word = allWords.tryFindWordByTxtEntry(txtWord) ?: run {
                div {
                    style = "color: red;"
                    +txtWord.kanjiOrKana
                }
                return@repeat
            }

            div {
                wordWithFurigana(word)
            }
        }
    }
}