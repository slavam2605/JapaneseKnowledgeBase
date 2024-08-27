package server.pages

import dict.WordEntry
import io.ktor.server.application.ApplicationCall
import kotlinx.html.*
import server.wordWithFurigana
import utils.isKanji
import kotlin.random.Random

class RandomWordPage(val dataset: Map<Char, List<WordEntry>>) : PageBuilderBase("/random_word") {
    private val random = Random.Default

    override fun HEAD.buildHead() {
        link("/random_word.css", "stylesheet", "text/css")
    }

    private fun allKanjiFromDataset(word: String): Boolean {
        for (char in word) {
            if (char.isKanji && char !in dataset)
                return false
        }
        return true
    }

    private fun getRandomWord(): WordEntry? {
        val keyIndex = random.nextInt(dataset.size)
        val value = dataset.values.toList()[keyIndex]
        val shuffledValue = value.shuffled(random)
        for (word in shuffledValue) {
            if (word.isCommon() && allKanjiFromDataset(word.text))
                return word
        }
        return null
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        for (index in 0 until 10) {
            val word = getRandomWord()
            if (word == null) {
                System.err.println("getRandomWord() returned null")
                continue
            }

            div("random_word") {
                wordWithFurigana(word) {
                    onMouseOver = "toggle(this, 'black')"
                    onMouseOut = "toggle(this, 'white')"
                }
            }
            script {
                unsafe {
                    +toggleScript
                }
            }
        }
    }

    private val toggleScript = """
        function toggle(element, color) {
            const rtElements = element.getElementsByTagName("rt");
            
            for (let x of rtElements) {
                x.style.color = color;
            }
        }
        
        for (let x of document.getElementsByTagName("rt")) {
            x.style.color = 'white';
        }
    """.trimIndent()
}