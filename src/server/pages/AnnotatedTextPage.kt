package server.pages

import dict.AllWordsList
import dict.WordEntry
import io.ktor.server.application.ApplicationCall
import kotlinx.html.*
import parser.JapaneseLexer
import parser.JapaneseToken
import server.wordWithFurigana
import utils.PathConstants
import utils.resolveResource

class AnnotatedTextPage(allWords: AllWordsList) : PageBuilderBase("/text") {
    private val text = resolveResource(PathConstants.sampleTextFile).readText()
    private val lexer = JapaneseLexer(text, allWords)

    override fun HEAD.buildHead() {
        link("/tooltip.css", "stylesheet", "text/css")
        link("/annotated_text.css", "stylesheet", "text/css")
    }

    private fun FlowContent.renderUnknownWord(token: JapaneseToken.UnknownWordToken) {
        span("unknown-word-token") {
            +token.text
        }
    }

    private fun FlowContent.renderCardHeader(word: WordEntry) {
        table("word-card-head") {
            tr {
                td("word-title") {
                    wordWithFurigana(word)
                }
                val tags = word.extraTags.filter {
                    !it.startsWith("Wanikani")
                }
                if (tags.isNotEmpty()) {
                    td("tags-block") {
                        tags.forEach { tag ->
                            div { +tag }
                        }
                    }
                }
            }
        }
    }

    private fun FlowContent.renderWord(token: JapaneseToken.WordToken) {
        span("word-token tooltip") {
            +token.text
            span("complex-tooltiptext") {
                table("dictionary-entry") {
                    token.possibleWords.forEach { word ->
                        tr {
                            td {
                                renderCardHeader(word)
                                unsafe {
                                    +word.meanings.joinToString(separator = "<br>")
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    private fun FlowContent.renderHiragana(token: JapaneseToken.HiraganaToken) {
        span("hiragana-token") {
            +token.text
        }
    }

    private fun FlowContent.renderOther(token: JapaneseToken.OtherToken) {
        if (token.text == "\n")
            br { }
        else
            +token.text
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        div {
            for (token in lexer.getTokens().take(400)) {
                when (token) {
                    is JapaneseToken.UnknownWordToken -> renderUnknownWord(token)
                    is JapaneseToken.WordToken -> renderWord(token)
                    is JapaneseToken.HiraganaToken -> renderHiragana(token)
                    is JapaneseToken.OtherToken -> renderOther(token)
                }.let { /* Exhaustiveness check */ }
            }
        }
    }
}